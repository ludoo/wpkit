<?php
/*
Plugin Name: WP Frontman Featured Images
Plugin URI: http://wpfrontman.com/
Description: Enable featured images regadless of the current WP theme's settings
Version: 0.1
Author: Ludovico Magnocavallo
Author URI: http://qix.it/
*/


class WPFFeaturedImages {
    
    var $wpf_options;
    
    function WPFFeaturedImages() {
        //add_filter('get_image_tag', array(&$this, 'get_image_tag'), 50);
        add_action('admin_menu', array(&$this, 'admin_menu'));
        add_action('after_setup_theme', array(&$this, 'after_setup_theme'));
    }
    
    function _bootstrap() {
        if (!is_null($this->wpf_options))
            return;
        $this->wpf_options = get_option('_wpf_featured_images', array());
        foreach (array('enabled'=>false, 'image_height'=>300) as $k=>$v) {
            if (!isset($this->wpf_options[$k]))
                $this->wpf_options[$k] = $v;
        }
        //$this->log('---' . var_export($this->wpf_options, true) . "\n");
    }
    
    function admin_menu() {
        if (function_exists('add_submenu_page')) {
            add_submenu_page(
                'plugins.php',
                'WPF Featured Images', 'WPF Featured Images',
                'activate_plugins', 'featured_images', array(&$this, 'admin_configuration')
            );
        }
    }
    
    function admin_configuration() {
        
        $this->_bootstrap();
        $message = null;
        
        if (isset($_POST['wpf_action'])) {
            $this->wpf_options['image_height'] = $_POST['wpf_image_height'];
            switch ($_POST['wpf_action']) {
                case 'enable':
                    $this->wpf_options['enabled'] = true;
                    $message = 'Featured images enabled.';
                    break;
                case 'disable':
                    $this->wpf_options['enabled'] = false;
                    $message = 'Featured images disabled.';
            }
            update_option('_wpf_featured_images', $this->wpf_options);
            //$this->log('updated options ' . var_export($this->wpf_options, true) . "\n");
        }
        echo "<div class=\"wrap\">\n";
        if ($message)
            echo '<div id="message" class="updated fade"><p>' . $message . '</p></div>';
        echo "<h2>WP Frontman Featured Images Configuration</h2>\n";
        
        // enable or disable preformatting
        echo '<form action="" method="post">';
        echo '<p><input type="text" size="6" name="wpf_image_height" id="wpf_image_height" value="' . $this->wpf_options['image_height'] . '" />';
        echo '<label for="wpf_image_height">Image Height</label></p>';
        if ($this->wpf_options['enabled'])
            echo '<input type="hidden" name="wpf_action" value="disable" /><p><input type="submit" class="button-primary" name="submit" value="Disable" /></p>';
        else
            echo '<input type="hidden" name="wpf_action" value="enable" /><p><input type="submit" class="button-primary" name="submit" value="Enable" /></p>';
        echo '</form>';
        echo "</div>\n";
    }
    
    function after_setup_theme() {
        $this->_bootstrap();
        if (!$this->wp_options['enabled'])
            return
        add_theme_support('post-thumbnails');
        define('HEADER_IMAGE_HEIGHT', (int)$this->wp_options['image_height']);
    }
    
    function log($s) {
        return;
        $f = fopen('/tmp/wpf.log', 'a+');
        fwrite($f, date("c") . " $s\n");
        fclose($f);
    }

}    


$wpf_featured_images =& new WPFFeaturedImages();

?>