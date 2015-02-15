<?php 


require_once implode(DIRECTORY_SEPARATOR, array(ABSPATH, 'wp-content', 'plugins', 'wp_frontman', 'lib', 'wpf_options.php'));


class WPFSiteOptionsTest extends PHPUnit_Framework_TestCase {
    
    function setUp() {
        $this->mu = is_multisite();
    }
    
    function test01Init() {
        $globals =& new WPFSiteOptions($this->mu);
        $this->assertTrue(!is_null($globals));
    }
    
    function test02Defaults() {
        $o =& new WPFSiteOptions($this->mu);
        $o->init_defaults();
        $this->assertTrue(is_array($o->defaults), "defaults not initialized");
        $this->assertTrue(array_key_exists('wp_root', $o->defaults), "no 'wp_root' key in defaults");
        $this->assertEquals($o->defaults['wp_root'], ABSPATH);
        $this->assertTrue(is_array($o->defaults['builtin_post_types']) && count($o->defaults['builtin_post_types']) > 0, "missing or empty 'builtin_post_types' in options");
        $this->assertTrue(is_array($o->defaults['builtin_taxonomies']) && count($o->defaults['builtin_taxonomies']) > 0, "missing or empty 'builtin_post_types' in options");
    }
    
    function test03InitOptions() {
        $o =& new WPFSiteOptions($this->mu);
        $o->_init_options();
        $this->assertTrue(is_array($o->options), "options not initialized");
        foreach (array('wp_root'=>ABSPATH, '_db_version'=>$o->db_version) as $k=>$v) {
            $this->assertTrue(array_key_exists($k, $o->options), "no '$k' key in options");
            $this->assertEquals($o->options[$k], $v);
        }
    }
    
    function test04Init() {
        if ($this->mu) {
            update_site_option('wp_frontman', null);
            $wp_opt = get_site_option('wp_frontman', null);
        } else {
            update_option('wp_frontman_site', null);
            $wp_opt = get_option('wp_frontman_site', null);
        }
        $this->assertTrue(!is_array($wp_opt), "WP option is array " . var_export($wp_opt, true));
        $o =& new WPFSiteOptions($this->mu);
        $this->assertTrue(!$o->_load_options(), "non empty options from _load_options");
        $ret = $o->init();
        $this->assertTrue($ret, "incorrect return value '$ret' from init");
        $this->assertTrue(is_array($o->options), "options not initialized");
        foreach (array('wp_root'=>ABSPATH, '_db_version'=>$o->db_version) as $k=>$v) {
            $this->assertTrue(array_key_exists($k, $o->options), "no '$k' key in options");
            $this->assertEquals($o->options[$k], $v);
        }
        $o =& new WPFSiteOptions($this->mu);
        $this->assertTrue(is_array($o->_load_options()), "empty options from _load_options");
        $ret = $o->init();
        $this->assertTrue(!$ret, "incorrect return value '$ret' from init");
        $this->assertTrue(is_array($o->options), "options not initialized");
        foreach (array('wp_root'=>ABSPATH, '_db_version'=>$o->db_version) as $k=>$v) {
            $this->assertTrue(array_key_exists($k, $o->options), "no '$k' key in options");
            $this->assertEquals($o->options[$k], $v);
        }
    }

    function test05Sync() {
        $o =& new WPFSiteOptions($this->mu);
        $this->assertTrue(is_array($o->_load_options()), "empty options from _load_options");
        $o->db_version = 999;
        $o->init_defaults();
        $o->defaults['dummy'] = 'dummy';
        unset($o->defaults['wp_root']);
        $o->defaults['builtin_post_types']['dummy'] = 'dummy';
        $o->init();
        $this->assertEquals($o->db_version, $o->options['_db_version'], "db versions do not match");
        $this->assertTrue(array_key_exists('dummy', $o->options), "no 'dummy' key in options: " . implode(', ', array_keys($o->options)));
        $this->assertEquals($o->options['dummy'], 'dummy', "incorrect value for 'dummy' option");
        $this->assertTrue(!array_key_exists('wp_root', $o->options), "key 'wp_root' still in options");
        $this->assertTrue(array_key_exists('dummy', $o->options['builtin_post_types']), "no key 'dummy' in 'builtin_post_types' option");
        $this->assertEquals($o->options['builtin_post_types']['dummy'], 'dummy', "incorrect value for 'dummy' in 'builtin_post_types' option");
    }
    
}



?>