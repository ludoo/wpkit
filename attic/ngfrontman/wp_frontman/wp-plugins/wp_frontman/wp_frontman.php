<?php
/*
Plugin Name: WP Frontman
Plugin URI: http://wpfrontman.com/
Description: Set various options for WP Frontman
Version: 0.1
Author: Ludovico Magnocavallo
Author URI: http://qix.it/

Trumpet icon (c) Sirea
http://www.softicons.com/free-icons/object-icons/musical-instruments-icons-by-sirea/trumpet-icon

*/


class WPFrontman {
    
    var $plugin_file;
    var $plugin_dir;
    var $plugin_url;
    var $content_url;
    var $mu = false;
    
    var $_init_blogs = false;

    var $site_options;
    var $blog_options;
    
    var $_skip_enabled_check_for = array('custom_taxonomies', 'custom_post_types');
    var $_modules = array();
    var $_active_module;
    
    function __construct() {
        $this->plugin_file = implode(DIRECTORY_SEPARATOR, array_slice(explode(DIRECTORY_SEPARATOR, __FILE__), -2));
        $this->plugin_dir = implode(DIRECTORY_SEPARATOR, array(WP_PLUGIN_DIR, dirname($this->plugin_file)));
        $this->content_url = $this->plugin_url = parse_url(WP_PLUGIN_URL, PHP_URL_PATH) . '/' . dirname($this->plugin_file);
        $t = parse_url($_SERVER['REQUEST_URI']);
        $this->admin_url = $t['scheme'] . $t['host'] . ($t['port'] ? ':' . $t['port'] : '') . $t['path'];
        // fuck WP, yet again
        $p = site_url();
        $p = parse_url($p ? $p : wp_guess_url(), PHP_URL_PATH);
        if ($p && substr($this->plugin_url, 0, strlen($p)) == $p)
            $this->content_url = substr($this->plugin_url, strlen($p));
        $this->lib_dir = implode(DIRECTORY_SEPARATOR, array($this->plugin_dir, 'lib', ''));
        //$this->templates_dir = $this->plugin_dir . DIRECTORY_SEPARATOR . 'templates';
        
        if (function_exists('is_multisite'))
            $this->mu = is_multisite();
        
        require_once "{$this->lib_dir}wpf_options.php";
        $this->site_options =& new WPFSiteOptions($this->mu);
        $this->blog_options =& new WPFBlogOptions($this->mu);
        
        if (function_exists('register_activation_hook'))
            register_activation_hook(implode(DIRECTORY_SEPARATOR, array_slice(explode(DIRECTORY_SEPARATOR, __FILE__), -2)), array(&$this, 'activate'));
        if (function_exists('add_action')) {
            if ($this->mu)
                add_action('wpmu_new_blog', array(&$this, 'action_new_blog'));
            add_action('plugins_loaded', array(&$this, 'action_plugins_loaded'));
            add_action('init', array(&$this, 'action_init'));
        }
        if (function_exists('add_filter'))
            add_filter('admin_footer_text', array(&$this, 'filter_admin_footer_text'), 10, 1);
    }
    
    function &_load_module($mod_name, $options=null, $enabled_only=false) {
        if (!is_string($mod_name) || !$mod_name)
            return;
        if (array_key_exists($mod_name, $this->_modules))
            return $this->_modules[$mod_name];
        if (is_null($options)) {
            if (!array_key_exists($mod_name, $this->blog_options->options))
                return;
            $options = $this->blog_options->options[$mod_name];
        }
        //echo "checking options<br />";
        if (!is_array($options))
            return;
        if (!in_array($mod_name, $this->_skip_enabled_check_for)) {
            if (!array_key_exists('enabled', $options))
                return;
            if ($enabled_only && !$options['enabled'])
                return;
        }
        //echo "including {$this->lib_dir}wpf_${mod_name}.php<br />";
        $classname = include_once "{$this->lib_dir}wpf_${mod_name}.php";
        if (!$classname || !is_string($classname))
            return;
        //echo "$mod_name - $classname<br />";
        $this->_modules[$mod_name] =& new $classname($this->mu, $this->plugin_url, $this->site_options, $this->blog_options);
        return $this->_modules[$mod_name];
    }
    
    function activate() {
        if ($this->site_options->init()) {
            // WP discards this instance as soon as it's finished activating it
            $this->site_options->options['_activate'] = true;
            $this->site_options->save();
        }
    }
    
    function _initialize_blogs() {
        if ($this->mu) {
            global $wpdb, $switched;
            foreach ($wpdb->get_results("SELECT * FROM {$wpdb->blogs} WHERE site_id = '{$wpdb->siteid}' and deleted=0", ARRAY_A) as $k=>$blog) {
                switch_to_blog($blog['blog_id']);
                $wp_rewrite =& new WP_Rewrite();
                $options =& new WPFBlogOptions($this->mu);
                $options->init();
            }
            while ($switched)
                restore_current_blog();
        } else {
            $this->blog_options->init();
        }
    }
    
    function filter_admin_footer_text($text) {
        return $text . ' &bull; <a href="http://wp-frontman.com/">WP Frontman</a> active';
    }
    
    function action_new_blog($blog_id, $user_id, $domain, $path, $site_id, $meta) {
        switch_to_blog($blog_id);
        $options =& new WPFBlogOptions($this->mu);
        $options->init();
        restore_current_blog();
    }
    
    function action_plugins_loaded() {
        $this->blog_options->init(true);
        if (!is_array($this->blog_options->options)) // only happens on first activation
            return;
        // emulate WP's plugin_page variable as it gets defined too late for our uses
        $active_module = null;
        if (isset($_GET['page'])) {
            $active_module = stripslashes($_GET['page']);
            $active_module = plugin_basename($active_module);
            $active_module = strlen($active_module) > 12 ? substr($active_module, 12) : null;
        }
        $this->_active_module = $active_module;
        foreach ($this->blog_options->options as $k=>$v) {
            if (!is_array($v))
                continue; // shortcut to skip calling the method
            // special-case preformatter or its ajax method won't be registered
            $mod =& $this->_load_module($k, $v, $k != 'preformatter' && $k != $active_module ? true : false);
            if (is_null($mod))
                continue;
            if (method_exists($mod, 'register_actions'))
                $mod->register_actions();
        }
    }
    
    function action_init() {
        $this->site_options->init();
        if (array_key_exists('_activate', $this->site_options->options) && $this->site_options->options['_activate']) {
            $this->_initialize_blogs();
            unset($this->site_options->options['_activate']);
            $this->site_options->save();
        }
        $this->blog_options->init();
        // TODO: check if we can detect when we are in site management mode, and if so
        //       add a simple menu entry with no leaves, or maybe use leaves to set
        //       site defaults
        if (current_user_can($this->mu ? 'manage_network_options' : 'manage_options')) {
            add_action('admin_menu', array(&$this, 'action_admin_menu'));
            add_action('admin_print_styles', array(&$this, 'action_admin_print_styles'));
            add_action('admin_print_scripts', array(&$this, 'action_admin_print_scripts'));
            add_action('admin_head', array(&$this, 'action_admin_head'));
        }
    }
    
    function action_admin_menu() {
        add_menu_page('WP Frontman', 'WP Frontman', 'manage_options', 'wp_frontman', array(&$this, 'render_menu'), $this->plugin_url . '/media/trumpet.png');
        add_submenu_page('wp_frontman', 'General &lsaquo; WP Frontman', 'General', 'manage_options', 'wp_frontman', array(&$this, 'render_menu'));
        $this->blog_options->init_defaults();
        foreach ($this->blog_options->defaults as $k=>$v) {
            if (!is_array($v) || !array_key_exists('label', $v)) // || !$this->blog_options[$k]['enabled'])
                continue;
            $label = $v['label'];
            add_submenu_page('wp_frontman', "$label &lsaquo; WP Frontman", $label, 'manage_options', 'wp_frontman_' . $k, array(&$this, 'render_menu'));
        }
        add_submenu_page('wp_frontman', "Custom Post Types &lsaquo; WP Frontman", 'Custom Post Types', 'manage_options', 'wp_frontman_custom_post_types', array(&$this, 'render_menu'));
        add_submenu_page('wp_frontman', "Custom Taxonomies &lsaquo; WP Frontman", 'Custom Taxonomies', 'manage_options', 'wp_frontman_custom_taxonomies', array(&$this, 'render_menu'));
        add_submenu_page('wp_frontman', "Debug &lsaquo; WP Frontman", 'Debug', 'manage_options', 'wp_frontman_debug', array(&$this, 'render_menu'));
    }
    
    function action_admin_print_styles() {
        wp_enqueue_style('wpf', "{$this->content_url}/css/wp_frontman.css");
    }
    
    function action_admin_print_scripts() {
        wp_enqueue_script('jquery');
    }
    
    function action_admin_head() {
        //echo "loading {$this->_active_module}<br />";
        //global $blog_id;
        //if (is_null($this->home))
        //    $this->home = get_option('home');
        echo "<script type=\"text/javascript\">\n";
        echo 'wpf_nonce = "' . wp_create_nonce('wp_frontman') . "\";\n";
        echo 'wp_root = "' . ABSPATH . '";' . "\n";
        echo "wpf_cache_endpoint = \"{$this->blog_options->options['cache']['endpoint']}\";\n";
        //echo "wpf_blog_id = $blog_id;\n";
        //echo "wpf_home = '" . $this->home . "';\n";
        echo "function wpf_indicator_on(id) { jQuery(id + '_info').toggleClass('wpf_error', false); jQuery(id + '_info').text('Sending request'); jQuery('html').css('cursor', 'wait'); jQuery(id).css('cursor', 'wait'); }\n";
        echo "function wpf_indicator_off(id, error, text) { jQuery('html').css('cursor', 'auto'); jQuery(id).css('cursor', 'pointer'); jQuery(id + '_info').toggleClass('wpf_error', error).text(text); }\n";
        echo "</script>\n";
        //die(var_export($mod, true));
        if (is_null($this->_active_module))
            return;
        $mod =& $this->_load_module($this->_active_module);
        if (!is_object($mod) || !method_exists($mod, 'action_admin_head'))
            return;
        echo $mod->action_admin_head();
    }
    
    function render_menu() {
        $this->wpf_log("render_menu " . var_export($this->_active_module, true));
        if (is_null($this->_active_module)) {
            $template = 'main.html';
            $vars = $this->get_main_vars();
        } else if ($this->_active_module == 'debug') {
            return $this->menu_debug();
        } else {
            $mod =& $this->_load_module($this->_active_module);
            $template = "section_{$this->_active_module}.html";
            $vars = $mod->get_menu_vars();
            $vars['module_url'] = $this->admin_url . '?page=wp_frontman_' . $this->_active_module;
        }
        require_once 'lib/h2o/h2o.php';
        
        $vars = array_merge(array(
            'mu'            => $this->mu,
            'plugin_url'    => $this->plugin_url,
            'is_mu_admin'   => $this->mu && current_user_can('manage_network_options'),
            'is_blog_admin' => current_user_can('manage_options'),
            'is_admin'      => current_user_can($this->mu ? 'manage_network_options' : 'manage_options')
        ), $vars);
        h2o::addFilter('pluralize', function ($word, $count, $singular='', $plural='s') {return $word . ($count == 1 ? $singular : $plural);});
        h2o::addFilter('boolean', function ($value) {return $value == 1 ? 'Y' : 'N';});
        $h2o =& new h2o($template, array('searchpath' => $this->plugin_dir . DIRECTORY_SEPARATOR . 'templates'));
        echo $h2o->render($vars);
    }
    
    function get_main_vars() {
        $messages = array();
        $this->site_options->init_defaults();
        if ($_POST && array_key_exists('action', $_POST)) {
            $site_changed = false;
            switch ($_POST['action']) {
                case 'global_options':
                    foreach (array('support_category_order', 'use_sendfile') as $k) {
                        $this->site_options->options[$k] = (array_key_exists($k, $_POST) && $_POST[$k] == 1 ? true : false);
                        $site_changed = true;
                    }
                    break;
                case 'urlconf':
                    $this->blog_options->options['urlconf'] = $_POST['urlconf'] ? $_POST['urlconf'] : null;
                    $this->blog_options->save();
                    break;
                case 'wp_constants':
                    foreach ($this->site_options->defaults as $k=>$v) {
                        if (substr($k, 0, 3) != 'wp_')
                            continue;
                        $this->wpf_log("setting $k to '$v' instead of '{$this->site_options->options[$k]}'");
                        $this->site_options->options[$k] = $v;
                        $site_changed = true;
                    }
                    break;
                /*
                case 'active_modules':
                    foreach ($this->blog_defaults as $k=>$v) {
                        if (!is_array($v) || !array_key_exists('enabled', $v))
                            continue;
                        $value = (array_key_exists($k, $_POST) && $_POST[$k] == 1 ? true : false);
                        $this->blog_options[$k]['enabled'] = $value;
                        $changed = true;
                    }
                    if ($changed)
                        $this->_update_blog_options();
                    break;
                */
            }
            if ($site_changed)
                $this->site_options->save();
            $this->wpf_log("changed site options $site_changed");
        }
        $wp_constants = array();
        foreach ($this->site_options->defaults as $k=>$v) {
            if (substr($k, 0, 3) != 'wp_')
                continue;
            $wp_constants[$k] = array(
                'label'     => ucfirst(implode(' ', explode('_', substr($k, 3)))),
                'default'   => $v,
                'value'     => $this->site_options->options[$k]
            );
        }
        return array(
            'title'             =>'WP Frontman - General Settings',
            'message'           => implode('<br />', $messages),
            'global_defaults'   => $this->site_options->defaults,
            'wp_constants'      => $wp_constants,
            'global_options'    => $this->site_options->options,
            'blog_options'      => $this->blog_options->options,
            'site_db_version'   => $this->site_options->db_version,
            'blog_db_version'   => $this->blog_options->db_version
        );
    }
    
    function menu_debug() {
        $this->site_options->init();
        global $current_site;
        echo 'site id: ' . (isset($current_site) ? $current_site->id : "not set") . '<br />';
        global $wp_rewrite;
        /*
        echo $wp_rewrite->permalink_structure . " front " . $wp_rewrite->front . " root " . $wp_rewrite->root . "<br />";
        echo '<h4>Builtin Taxonomies</h4>';
        echo '<pre>';
        var_export($this->site_options->options['builtin_taxonomies']);
        echo '</pre>';
        echo '<h4>Custom Taxonomies</h4>';
        echo '<pre>';
        var_export($this->blog_options->options['custom_taxonomies']);
        echo '</pre>';
        */
        /*
        echo '<h4>Post Types</h4>';
        global $wp_post_types;
        echo '<pre>';
        var_export($wp_post_types);
        echo '</pre>';
        */
        /*
        echo '<h4>Blog options</h4>';
        echo '<pre>';
        var_export($this->blog_options->options);
        echo '</pre>';
        echo '<h4>Site options</h4>';
        echo '<pre>';
        var_export($this->site_options->options);
        echo '</pre>';
        echo '<h4>Rewrite Debug</h4>';
        echo '<pre>';
        global $wp_rewrite;
        $wp_rewrite->use_verbose_rules = true;
        var_export($wp_rewrite->generate_rewrite_rules($wp_rewrite->permalink_structure, 1));
        $wp_rewrite->use_verbose_rules = false;
        echo '</pre>';
        */
        echo '<h4>Rewrite Rules Option</h4>';
        echo '<pre>';
        var_export(get_option('rewrite_rules'));
        echo '</pre>';
        /*
        echo '<h4>Serialized Rewrite Rules Option</h4>';
        echo '<pre>';
        echo serialize(get_option('rewrite_rules'));
        echo '</pre>';
        */
    }
    
    function wpf_log($s) {
        $f = fopen('/tmp/wpf.log', 'a+');
        fwrite($f, date("c") . " $s\n");
        fclose($f);
    }

}


class WPFModule {
    
    var $mu;
    var $plugin_url;
    var $site_options;
    var $blog_options;
    
    function __construct($mu, $plugin_url, &$site_options, &$blog_options) {
        $this->mu = $mu;
        $this->plugin_url = $plugin_url;
        $this->site_options =& $site_options;
        $this->blog_options =& $blog_options;
    }
    
    function register_actions() {
        //error_log("Override register_actions in " . get_class($this));
    }
    
    function get_menu_vars() {
        return array();
    }
    
    function wpf_log($s) {
        $f = fopen('/tmp/wpf.log', 'a+');
        fwrite($f, date("c") . ' [' . get_class($this) . " module] $s\n");
        fclose($f);
    }

}


if (function_exists('is_admin') && is_admin()) {
    $wpf = new WPFrontman();
}

?>
