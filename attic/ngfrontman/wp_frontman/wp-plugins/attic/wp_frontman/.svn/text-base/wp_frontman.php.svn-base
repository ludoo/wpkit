<?php
/*
Plugin Name: WP Frontman
Plugin URI: http://wpfrontman.com/
Description: Set various options for WP Frontman
Version: 0.1
Author: Ludovico Magnocavallo
Author URI: http://qix.it/
*/


class WPFrontman {
    
    var $plugin_file;
    var $plugin_dir;
    var $plugin_url;
    var $options;
    var $site_options;
    var $message = array();
    var $message_status = 'updated';
    var $defaults = array(
        'db_version'            => 28,
        'custom_favicon'        => false,
        'custom_robots'         => false,
        'categories_as_sets'    => null,
        'cache'                 => array(
            'label'                 => 'Cache',
            'enabled'               => false,
            'destination'           => null
        ),
        'preformatter'          => array(
            'label'                 => 'Preformatting',
            'max_id'                => 0,
            'batch_size'            => 500,
            'batch_done'            => false,
            'batch_running'         => false,
            'relative_urls'         => true
        ),
        'feedburner'            => array(
            'label'                 => 'Feedburner',
            'enabled'               => false,
            'url'                   => null,
            'url_requests'          => "feed/atom\nfeed/rss2\n",
            'comments_url'          => null,
            'comments_url_requests' => ""
            ),
        'featured_images'       => array(
            'label'                 => 'Featured Images',
            'enabled'               => false,
            'sizes'                 => array()
        ),
        'analytics'             => array(
            'label'                 => 'Analytics',
            'enabled'               => false,
            'token'                 => null,
            'session_token'         => null,
            'account_name'          => null,
            'account_id'            => null,
            'filter'                => null
        ),
        'custom_taxonomies'     => array(
            'label'                 => 'Taxonomies',
            'enabled'               => false,
            'custom_taxonomies'     => array()
        )
    );
    var $default_taxonomies = array();
    
    function WPFrontman() {
        $this->plugin_file = implode(DIRECTORY_SEPARATOR, array_slice(explode(DIRECTORY_SEPARATOR, __FILE__), -2));
        $this->plugin_dir = implode(DIRECTORY_SEPARATOR, array(WP_PLUGIN_DIR, dirname($this->plugin_file)));
        $this->plugin_url = parse_url(WP_PLUGIN_URL, PHP_URL_PATH) . '/' . dirname($this->plugin_file);
        $this->templates_dir = $this->plugin_dir . DIRECTORY_SEPARATOR . 'templates';
        register_activation_hook($this->plugin_file, array($this, 'activate'));
        add_action('admin_menu', array(&$this, 'admin_menu'));
        add_action('admin_print_styles', array(&$this, 'admin_print_styles'));
        add_action('admin_print_scripts', array(&$this, 'admin_print_scripts'));
        add_action('admin_head', array(&$this, 'admin_head'));
        add_action('after_setup_theme', array(&$this, 'after_setup_theme'));
        add_action('init', array(&$this, 'init_taxonomies'));
    }
    
    function _taxonomy_to_array(&$taxonomy) {
        return array(
            'label'                 => $taxonomy->label,
            'public'                => $taxonomy->public,
            'show_ui'               => $taxonomy->show_ui,
            'hierarchical'          => $taxonomy->hierarchical,
            'update_count'          => $taxonomy->update_count_callback == '_update_post_term_count' ? true : false,
            'rewrite_hierarchical'  => is_array($taxonomy->rewrite) && $taxonomy->rewrite['hierarchical'] ? true : false,
            'rewrite_slug'          => is_array($taxonomy->rewrite) && $taxonomy->rewrite['slug'] ? $taxonomy->rewrite['slug'] : null,
            'rewrite_with_front'    => is_array($taxonomy->rewrite) && $taxonomy->rewrite['with_front'] ? $taxonomy->rewrite['with_front'] : true,
            'object_type'           => $taxonomy->object_type ? $taxonomy->object_type : null
        );
    }
    
    function init_taxonomies() {
        // load custom taxonomies here
        $this->_bootstrap_options('init');
        global $wp_taxonomies;
        foreach ($wp_taxonomies as $k=>$v) {
            if ($v->_builtin)
                $this->default_taxonomies[$k] = $this->_taxonomy_to_array($v);
            else
                $this->defaults['custom_taxonomies']['custom_taxonomies'][$k] = $this->_taxonomy_to_array($v);
        }
        if ($this->defaults['custom_taxonomies']['custom_taxonomies'] && !$this->options['custom_taxonomies']['custom_taxonomies']) {
            // options have already been bootstrapped by someone else, probably after_setup_theme
            // store custom taxonomies as it's the first time we encounter them
            $this->options['custom_taxonomies']['custom_taxonomies'] = $this->defaults['custom_taxonomies']['custom_taxonomies'];
            update_option('wp_frontman', $this->options);
            $this->message[] = "Custom taxonomies migrated from WP, options saved";
        }
//        var_export($this->defaults['custom_taxonomies']['custom_taxonomies']);
    }
    
    function _legacy_options() {
        // use options from the old plugins as defaults if we have any
        $analytics = get_option('_wpf_analytics', null);
        if (is_array($analytics) && $analytics) {
            foreach ($analytics as $k=>$v) {
                if (array_key_exists($k, $this->options['analytics']))
                    $this->options['analytics'][$k] = $v;
            }
            delete_option('_wpf_analytics');
        }
    }
    
    function _upgrade_options() {

        $old_version = $this->options['db_version'];
        
        switch ($old_version) {
            default:
                $this->options['db_version'] = $this->defaults['db_version'];
        }
        
        foreach ($this->defaults as $k=>$v) {
            if (!array_key_exists($k, $this->options)) {
                $this->options[$k] = $v;
            } else if (is_array($v)) {
                if (!is_array($this->options[$k])) {
                    $this->options[$k] = $v;
                } else {
                    foreach ($v as $kk=>$vv) {
                        if (!array_key_exists($kk, $this->options[$k]) || $kk == 'label')
                            $this->options[$k][$kk] = $vv;
                    }
                }
            }
        }
        
        foreach ($this->options as $k=>$v) {
            if (!array_key_exists($k, $this->defaults)) {
                unset($this->options[$k]);
            } else if (is_array($v)) {
                if (!is_array($this->defaults[$k])) {
                    $this->options[$k] = $this->defaults[$k];
                } else {
                    foreach ($v as $kk=>$vv) {
                        if (!array_key_exists($kk, $this->defaults[$k]))
                            unset($this->options[$k][$kk]);
                    }
                }
            }
        }

        $this->_legacy_options();
        
        update_option('wp_frontman', $this->options);
        $this->message[] = "Database version updated from version $old_version to {$this->options['db_version']}.";
        $this->log("upgraded");
    }
    
    function _bootstrap_options($caller=null) {
        if (!is_null($this->site_options))
            return;
        $site_options = array();
        foreach (get_site_option('wp_frontman', array()) as $k=>$v) {
            if (substr($k, 0, 3) == 'wp_' && (strrpos($k, '_key') == 0 || strrpos($k, '_salt') == 0))
                $_v = $v !== null ? '[hidden for security purposes]' : 'not set';
            else
                $_v = $v === false ? 'false' : ($v === true ? 'true' : $v);
            $site_options[$k] = array(
                'label'=>str_replace('_', ' ', $k),
                'value'=>$v, 'descriptive_value'=>$_v
            );
        }
        $this->site_options = $site_options;
        $this->options = get_option('wp_frontman', array());
        if ($this->options['db_version'] < $this->defaults['db_version'])
            $this->_upgrade_options();
        // set defaults controlled by WP with add_theme_support and custom taxonomies
        global $_wp_theme_features, $_wp_additional_image_sizes;
        if (is_array($_wp_theme_features) && array_key_exists('post_thumbnails', $_wp_theme_features))
            $this->defaults['featured_images']['enabled'] = true;
        if ($_wp_additional_image_sizes)
            $this->defaults['featured_images']['sizes'] = $_wp_additional_image_sizes;
        // merge defaults and options
        foreach ($this->defaults as $k=>$v) {
            if (!array_key_exists($k, $this->options) || is_null($this->options[$k])) {
                $this->options[$k] = $v;
                continue;
            }
            if (!is_array($v))
                continue;
            foreach ($v as $kk=>$vv) {
                if (!array_key_exists($kk, $this->options[$k]) || is_null($this->options[$k][$kk])) {
                    $this->options[$k][$kk] = $vv;
                } else if (is_array($vv)) {
                    if (is_array($this->options[$k][$kk]))
                        $this->options[$k][$kk] = array_merge($vv, $this->options[$k][$kk]);
                    else
                        $this->options[$k][$kk] = $vv;
                }
            }
        }
        // buggy
        //$this->options = array_merge_recursive($this->defaults, $this->options);
        
        // set fake enabled keys for the options controlled by the network settings
        $this->options['preformatter']['enabled'] = $this->site_options['preformatter']['value'];
        $this->options['cache']['enabled'] = (bool)$this->site_options['cache_destination']['value'];
        $this->options['cache']['destination'] = $this->site_options['cache_destination']['value'];
    }

    function admin_menu() {
        $page = add_options_page('WP Frontman: Options', 'WP Frontman', 'manage_options', 'wpf_options', array(&$this, 'options_page'));
        //add_action("admin_print_scripts-$page", array($this, 'admin_print_scripts'));
    }
    
    function admin_print_styles() {
        wp_enqueue_style('wpf', "{$this->plugin_url}/css/wp_frontman.css");
        //wp_enqueue_style('wpf_jquery-ui', "{$this->plugin_url}/css/start/jquery-ui-1.8.15.custom.css");
    }
    
    function admin_print_scripts() {
        wp_enqueue_script('wpf', "{$this->plugin_url}/js/wp_frontman.js", array('jquery'));
        //wp_enqueue_script('wpf_jquery-ui-progressbar', "{$this->plugin_url}/js/jquery.ui.progressbar.min.js", array('jquery-ui-widget'), '1', true);
    }
    
    function admin_head() {
        global $blog_id;
        $this->_bootstrap_options('admin_head');
        echo "<script type=\"text/javascript\">\n";
        echo 'wpf_nonce = "' . wp_create_nonce('wp_frontman') . "\";\n";
        //echo "wpf_cache_destination = \"{$this->site_options['cache_destination']['value']}\";\n";
        echo "wpf_blog_id = $blog_id;\n";
        echo "wpf_home = '" . get_option('home') . "';\n";
        echo "</script>\n";
    }
    
    function after_setup_theme() {
        $this->_bootstrap_options('after_setup_theme');
        if (!$this->options['featured_images']['enabled'])
            return;
        add_theme_support('post-thumbnails');
        foreach ($this->options['featured_images']['sizes'] as $k=>$v) {
            if ($k == 'default')
                set_post_thumbnail_size($v['width'], $v['height'], $v['crop']);
            else
                add_image_size($k, $v['width'], $v['height'], $v['crop']);
        }
    }
    
    function options_page() {
        global $blog_id;
        
        $this->_bootstrap_options('options_page');

        // track changes and update options if needed
        require_once 'h2o/h2o.php';
        
        $uri_tokens = parse_url($_SERVER['REQUEST_URI']);
        
        $vars = array(
            'blog_id'       => $blog_id,
            'admin_url'     => parse_url(admin_url(), PHP_URL_PATH),
            'base_url'      => $this->plugin_url,
            'plugin_url'    => $uri_tokens['path'] . '?page=wpf_options',
            'site_options'  => $this->site_options,
            'section_slug'  => 'main',
            'section_label' => '',
            'section_vars'  => null
        );
        $template = 'main.html';
        foreach ($this->options as $slug=>$data) {
            if (!is_array($data))
                continue;
            if (strpos($uri_tokens['query'], "section=$slug")) {
                $vars['section_slug'] = $slug;
                $vars['section_label'] = $data['label'];
                $template = "section_$slug.html";
                break;
            }
        }
        $vars['section_vars'] =& call_user_func(array($this, "_options_page_do_{$vars['section_slug']}"));
        $vars['options'] = $this->options;
        $vars['message'] = implode('<br />', $this->message);
        $vars['message_status'] = $this->message_status;
        h2o::addFilter('pluralize', function ($word, $count, $singular='', $plural='s') {return $word . ($count == 1 ? $singular : $plural);});
        $h2o =& new h2o($template, array('searchpath' => $this->templates_dir));
        echo $h2o->render($vars);
    }
    
    function _options_page_check_post($keys, $options_branch=null) {
        if (!$_POST) return;
        if ($options_branch) {
            $opts =& $this->options[$options_branch];
            $defaults =& $this->defaults[$options_branch];
        } else {
            $opts =& $this->options;
            $defaults =& $this->defaults;
        }
        foreach ($keys as $k) {
            $default = $defaults[$k];
            $v = array_key_exists($k, $_POST) ? $_POST[$k] : null;
            if (is_bool($default))
                $v = is_null($v) ? false : true;
            else
                $v = is_null($v) ? $default : $v;
            $opts[$k] = $v;
        }
        update_option('wp_frontman', $this->options);
        $this->message[] = "Options updated";
    }
    
    function &_options_page_do_main() {
        $this->_options_page_check_post(array('custom_favicon', 'custom_robots', 'categories_as_sets'));
    }
    
    function &_options_page_do_cache() { }
    
    function &_options_page_do_preformatter() {
        $this->_options_page_check_post(array('relative_urls'), 'preformatter');
    }
    
    function &_options_page_do_featured_images() {
        $opts = array();
        if ($_POST['additional_size']) {
            foreach (array('name', 'width', 'height', 'crop') as $k) {
                if (array_key_exists($k, $_POST) && $_POST[$k])
                    $opts[$k] = $_POST[$k];
            }
            if (!$opts['name']) {
                $this->message[] = "You need at least a name and one of the dimensions to set a new size.";
            } else {
                if ($opts['width'])
                    $opts['width'] = (int)$opts['width'];
                else
                    $opts['width'] = 0;
                if ($opts['height'])
                    $opts['height'] = (int)$opts['height'];
                else
                    $opts['height'] = 0;
                if ($opts['width'] == 0 && $opts['height'] == 0) {
                    $this->message[] = "You need at least one dimension to set a new size.";
                } else if ($opts['width'] != 0 && $opts['width'] . '' != $_POST['width']) {
                    $this->message[] = "Cannot set size, width is not a number";
                } else if ($opts['height'] != 0 && $opts['height'] . '' != $_POST['height']) {
                    $this->message[] = "Cannot set size, height is not a number";
                } else {
                    $crop = (bool)$opts['crop'];
                    $this->options['featured_images']['sizes'][$opts['name']] = array('width'=>$opts['width'], 'height'=>$opts['height'], 'crop'=>$crop);
                    update_option('wp_frontman', $this->options);
                    if ($opts['name'] == 'default')
                        set_post_thumbnail_size($opts['width'], $opts['height'], $crop);
                    else
                        add_image_size($opts['name'], $opts['width'], $opts['height'], $crop);
                    $this->message[] = "Size {$opts['name']} set";
                    $opts = array();
                }
            }
        } else {
            $this->_options_page_check_post(array('enabled'), 'featured_images');
        }
        //if ($this->options['featured_images']['enabled'] && !array_key_exists('default', $this->options['featured_images']['sizes']))
        //    $this->message .= 'Remember to set at least a default size';
        return $opts;
    }
    
    function &_options_page_do_analytics() {
        if (array_key_exists('token', $_GET) && $_GET['token'] && $_GET['token'] != $this->options['analytics']['token']) {
            $this->options['analytics']['token'] = $_GET['token'];
            update_option('wp_frontman', $this->options);
        }
        if ($_POST && array_key_exists('analytics_reset', $_POST) && $_POST['analytics_reset']) {
            $this->options['analytics']['token'] = null;
            $this->options['analytics']['session_token'] = null;
            update_option('wp_frontman', $this->options);
        }
        if ($_POST && array_key_exists('account_name', $_POST) && $_POST['account_name'] != $this->options['analytics']['account_name'])
            $this->options['analytics']['account_id'] = null;
        $this->_options_page_check_post(array('enabled', 'account_id', 'filter'), 'analytics');
        $vars = array(
            'request_url'       =>  urlencode(get_option('siteurl') . $_SERVER['REQUEST_URI']),
        );
        if ($this->options['analytics']['enabled']) {
            global $wpdb, $blog_id;
            $vars['status'] = $wpdb->get_results("select * from " . DB_NAME . "_wpf_job where blog_id=$blog_id order by id desc limit 5", ARRAY_A);
            $vars['daily'] = $wpdb->get_results("select * from " . DB_NAME . "_wpf_analytics_post_daily where blog_id=$blog_id and day=cast(now() as date) - interval 1 day order by visitors desc, pageviews desc limit 5", ARRAY_A);
            if ($vars['daily']) {
                $posts = array();
                $q = "select ID as id, post_date as date, post_title as title, cast(post_date as date) as day from {$wpdb->posts} where ID in (" . implode(',', array_map(function ($v) { return $v['post_id']; }, $vars['daily'])) . ")";
                foreach ($wpdb->get_results($q, ARRAY_A) as $k=>$v)
                    $posts[$v['id']] = $v;
                foreach ($vars['daily'] as $k=>$v)
                    $vars['daily'][$k]['post'] = $posts[$v['post_id']];
            }
            $vars['weekly'] = $wpdb->get_results("select * from " . DB_NAME . "_wpf_analytics_post_aggregate where blog_id=$blog_id and year=-1 and month=-1 order by visitors desc, pageviews desc limit 5", ARRAY_A);
            if ($vars['weekly']) {
                $posts = array();
                $q = "select ID as id, post_date as date, post_title as title, cast(post_date as date) as day from {$wpdb->posts} where ID in (" . implode(',', array_map(function ($v) { return $v['post_id']; }, $vars['weekly'])) . ")";
                foreach ($wpdb->get_results($q, ARRAY_A) as $k=>$v)
                    $posts[$v['id']] = $v;
                foreach ($vars['weekly'] as $k=>$v)
                    $vars['weekly'][$k]['post'] = $posts[$v['post_id']];
            }
        }
        return $vars;
    }
    
    function &_options_page_do_custom_taxonomies() {
        $this->_options_page_check_post(array('enabled'), 'custom_taxonomies');
        $vars = array(
            'default_taxonomies'=>$this->default_taxonomies,
            // TODO: add support for custom posts, etc.
            'obj_types'=>array('post', 'link')
        );
        if (array_key_exists('edit', $_GET)) {
            $taxonomy = $_GET['edit'];
            if (array_key_exists($taxonomy, $this->options['custom_taxonomies']['custom_taxonomies'])) {
                $vars['name'] = $taxonomy;
                foreach ($this->options['custom_taxonomies']['custom_taxonomies'][$taxonomy] as $k=>$v)
                    $vars[$k] = $v;
            } else {
                $this->message[] = "No custom taxonomy '$taxonomy'";
            }
        }
        if ($_POST) {
            // check for a custom taxonomy
            $taxonomy = array('name', 'label');
        }
        return $vars;
    }
    
    function &_options_page_do_feedburner() {
        $keys = array_filter(array_keys($this->defaults['feedburner']), function ($k) { return $k != 'label'; });
        $this->_options_page_check_post($keys, 'feedburner');
        $home = get_option('home');
        if (substr($home, -1) != '/')
            $home .= '/';
        $vars = array('home'=>$home);
        return $vars;
    }
    
    function activate() {
        $options = get_option('wp_frontman');
        if (!$options) {
            // bootstrap
            $options = $this->defaults;
            // import options from the old separate plugins
            $opt = get_option('wpf_cache_destination');
            //$this->log("wpf_cache_destination " . var_export($opt, true));
            if ($opt) {
                $options['cache']['destination'] = $opt;
                $options['cache']['enabled'] = true;
            }
            foreach (array('_wpf_preformatter', '_wpf_featured_images', 'wpf_feedburner') as $opt_name) {
                $opt = get_option($opt_name);
                //$this->log("$opt_name " . var_export($opt, true));
                $opt_name = substr($opt_name, $opt_name[0] == '_' ? 5 : 4);
                if ($opt) {
                    $options_branch =& $options[$opt_name];
                    $defaults_branch = $this->defaults[$opt_name];
                    foreach ($opt as $k=>$v) {
                        if (!array_key_exists($k, $defaults_branch))
                            continue;
                        $options_branch[$k] = $v;
                    }
                }
            }
            // TODO: clear old options once the plugin is complete and working
        }
        update_option('wp_frontman', $options);
    }
    
    function log($s) {
        $f = fopen('/tmp/wpf.log', 'a+');
        fwrite($f, date("c") . " $s\n");
        fclose($f);
    }

}

if (function_exists('is_admin') && is_admin()) {
    $wpf =& new WPFrontman();
}

?>
