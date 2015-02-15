<?php 


require_once implode(DIRECTORY_SEPARATOR, array(ABSPATH, 'wp-content', 'plugins', 'wp_frontman', 'lib', 'wpf_options.php'));


class WPFBlogOptionsTest extends PHPUnit_Framework_TestCase {
    
    function setUp() {
        $this->mu = is_multisite();
    }
    
    function test01Init() {
        $o =& new WPFBlogOptions($this->mu);
        $this->assertTrue(!is_null($o));
    }
    
    function test02Defaults() {
        $o =& new WPFBlogOptions($this->mu);
        global $wp_rewrite;
        $o->init_defaults();
        $this->assertTrue(is_array($o->defaults), "defaults not initialized");
        $this->assertEquals($o->defaults['rewrite']['author_base'], 'author', "incorrect value {$o->defaults['rewrite']['author_base']} for 'author_base' in 'rewrite' default");
        $this->assertTrue($o->defaults['cache']['enabled'], "cache not enabled");
        $u = parse_url(get_option('home'));
        $e = parse_url($o->defaults['cache']['endpoint']);
        $this->assertEquals($u['scheme'], $e['scheme'], "cache endpoint scheme '{$e['scheme']}' different from home scheme");
        $this->assertEquals($u['host'], $e['host'], "cache endpoint host '{$e['host']}' different from home host");
        $this->assertEquals(substr($e['path'], 0, strlen($u['path'])), $u['path'], "cache endpoint path '{$e['path']}' not a superset of home path");
        $this->assertEquals(substr($e['path'], -11), '/wpf_cache/', "cache endpoint path '{$e['path']}' does not end in '/wpf_cache/'");
    }
    
    function test03InitOptions() {
        $o =& new WPFBlogOptions($this->mu);
        $o->_init_options();
        $this->assertTrue(is_array($o->options), "options not initialized");
        $this->assertEquals($o->options['rewrite']['author_base'], 'author', "incorrect value {$o->options['rewrite']['author_base']} for 'author_base' in 'rewrite' option");
    }

    function test04Init() {
        update_option('wp_frontman', null);
        $wp_opt = get_option('wp_frontman', null);
        $this->assertTrue(!is_array($wp_opt), "WP option is array " . var_export($wp_opt, true));
        $o =& new WPFBlogOptions($this->mu);
        $this->assertTrue(!$o->_load_options(), "non empty options from _load_options");
        $o->init();
        $this->assertTrue(is_array($o->options), "options not initialized");
        $this->assertEquals($o->options['rewrite']['author_base'], 'author', "incorrect value {$o->options['rewrite']['author_base']} for 'author_base' in 'rewrite' option");
        $wp_opt = get_option('wp_frontman', null);
        $this->assertTrue(is_array($wp_opt), "WP option is not an array " . var_export($wp_opt, true));
        $o =& new WPFBlogOptions($this->mu);
        $this->assertTrue(is_array($o->_load_options()), "empty options from _load_options");
        $o->init();
        $this->assertTrue(is_array($o->options), "options not initialized");
        $this->assertEquals($o->options['rewrite']['author_base'], 'author', "incorrect value {$o->options['rewrite']['author_base']} for 'author_base' in 'rewrite' option");
    }

    function test05Sync() {
        $o =& new WPFBlogOptions($this->mu);
        $this->assertTrue(is_array($o->_load_options()), "empty options from _load_options");
        $o->db_version = 999;
        $o->init_defaults();
        $o->defaults['dummy'] = 'dummy';
        unset($o->defaults['cache']);
        $o->defaults['preformatter']['dummy'] = 'dummy';
        $o->init();
        $this->assertEquals($o->db_version, $o->options['_db_version'], "db versions do not match");
        $this->assertTrue(array_key_exists('dummy', $o->options), "no 'dummy' key in options: " . implode(', ', array_keys($o->options)));
        $this->assertEquals($o->options['dummy'], 'dummy', "incorrect value for 'dummy' option");
        $this->assertTrue(!array_key_exists('cache', $o->options), "key 'cache' still in options");
        $this->assertTrue(array_key_exists('dummy', $o->options['preformatter']), "no key 'dummy' in 'preformatter' option");
        $this->assertEquals($o->options['preformatter']['dummy'], 'dummy', "incorrect value for 'dummy' in 'preformatter' option");
    }
    
    function test06InitLoadOnly() {
        $o =& new WPFBlogOptions($this->mu);
        $this->assertTrue(is_array($o->_load_options()), "empty options from _load_options");
        $o->init(true);
        $this->assertTrue(is_array($o->options), "options not initialized");
        $this->assertEquals($o->_options_synced, false, "options synced");
        $this->assertTrue(is_null($o->defaults), "defaults have been initialized");
        $o->db_version = 999;
        $o->init();
        $this->assertTrue(is_array($o->options), "options not initialized");
        $this->assertEquals($o->_options_synced, true, "options not synced");
        $this->assertTrue(is_array($o->defaults), "defaults have not been initialized");
    }
    
}


?>
