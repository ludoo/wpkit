<?php
/*
Plugin Name: WP Frontman Preformatter
Plugin URI: http://wpfrontman.com/
Description: Stores a formatted copy of the post contents in the database
Version: 0.1
Author: Ludovico Magnocavallo
Author URI: http://qix.it/
*/


class Preformatter {

    var $regexp = null;
    var $port = null;

    function Preformatter() {
        $this->home = get_option('home');
        add_action('admin_menu', array(&$this, 'preformatter_submenu'));
        add_action('save_post', array(&$this, 'save_post'), 9, 2);
        add_action('wp_ajax_wpf_batch_preformatting', array(&$this, 'ajax_preformatting'));
    }
    
    function _bootstrap() {
        if (!is_null($this->regexp))
            return true;
        if (is_null($this->home))
            return false;
        $t = parse_url($this->home);
        $this->regexp = '#<(?:img|a)\s+[^>]*[src|href]=\\\?["\'](' . $t['scheme'] . '://' . $t['host'] . '[^"\'\\\]+)#i';
        $this->port = isset($t['port']) ? $t['port'] : null;
    }
    
    function save_post($post_id, $post) {
        if ($post->post_type != 'post')
            return;
        global $wpdb;
        $wpf_preformatter = get_option('_wpf_preformatter');
        if (!isset($wpf_preformatter['enabled']) || !$wpf_preformatter['enabled']) {
            if ($post->post_content_filtered)
                $wpdb->query("UPDATE $wpdb->posts SET post_content_filtered = '' WHERE ID = '$post_id'");
            return;
        }
        if ($post->post_status != 'publish') {
            $wpdb->query("UPDATE $wpdb->posts SET post_content_filtered = '' WHERE ID = '$post_id'");
            return;
        }
        $relative_urls = isset($wpf_preformatter['relative_urls']) && $wpf_preformatter['relative_urls'];
        $this->_preformat($post_id, $post->post_content, $relative_urls);
    }
    
    function _relativize($content) {
        if (!$this->_bootstrap())
            return $content;
        preg_match_all($this->regexp, $content, $matches);
        if (isset($matches[1])) {
            foreach ($matches[1] as $url) {
                $t = parse_url($url);
                if (isset($t['port']) && $t['port'] != $this->port)
                    continue;
                $repl = $t['path'];
                if ($t['query'])
                    $repl .= "?{$t['query']}";
                if ($t['fragment'])
                    $repl .= "?{$t['fragment']}";
                $content = str_replace($url, $repl, $content);
            }
        }
        return $content;
    }

    function _preformat($post_id, $content, $relative_urls=false) {
        global $wpdb;
        if ($relative_urls)
            $content = $this->_relativize($content);
        $preformatted = apply_filters('the_content', preg_replace('/<!--more(.*?)?-->/', '<span id="more-' . $post_id . '"></span>', stripslashes($content)));
        $content_tokens = get_extended(stripslashes($content));
        if ($content_tokens['extended'])
            $summary = apply_filters('the_content', $content_tokens['main']);
        else
            $summary = '';
        
        # TODO: auto-build a nice excerpt instead of the sucky one generated by WP

        $query = "UPDATE $wpdb->posts SET post_content_filtered = concat('". addslashes($summary) . "', char(0), '" . addslashes($preformatted) . "', char(0), unix_timestamp(post_modified_gmt)) WHERE ID = '$post_id'";
        $res = $wpdb->query($query);
        if ($res === false)
            $wpdb->query("UPDATE $wpdb->posts SET post_content_filtered = '' WHERE ID = '$post_id'");
    }
    
    function preformatter_submenu() {
        if (function_exists('add_submenu_page')) {
            add_submenu_page(
                'plugins.php',
                'WPF Preformatter Configuration', 'WPF Preformatter',
                'activate_plugins', 'preformatter', array(&$this, 'preformatter_configuration')
            );
        }
    }
    
    function _get_option() {
        $wpf_preformatter = get_option('_wpf_preformatter', array());
        foreach (array('enabled'=>false, 'max_id'=>null, 'batch_size'=>500, 'batch_done'=>false, 'batch_running'=>false, 'relative_urls'=>true) as $k=>$v) {
            if (!isset($wpf_preformatter[$k]))
                $wpf_preformatter[$k] = $v;
        }
        return $wpf_preformatter;
    }
    
    function preformatter_configuration() {
        
        global $wpdb;
        
        $wpf_preformatter = $this->_get_option();
        $message = '';
        $error = false;

        if (isset($_POST['wpf_action'])) {
            switch ($_POST['wpf_action']) {
                case 'enable':
                    $wpf_preformatter['enabled'] = true;
                    if (!isset($_POST['wpf_relative_urls']) || !$_POST['wpf_relative_urls'])
                        $wpf_preformatter['relative_urls'] = false;
                    else
                        $wpf_preformatter['relative_urls'] = true;
                    update_option('_wpf_preformatter', $wpf_preformatter);
                    $message = 'Preformatting enabled.';
                    break;
                case 'disable':
                    $wpf_preformatter['enabled'] = false;
                    $message = 'Preformatting disabled.';
                case 'remove':
                    $wpf_preformatter['batch_running'] = false;
                    $wpf_preformatter['batch_done'] = false;
                    $wpf_preformatter['batch_size'] = 500;
                    $wpf_preformatter['max_id'] = null;
                    $message .= ($message ? ' ' : '');
                    $res = $wpdb->query("update {$wpdb->posts} set post_content_filtered=NULL");
                    if ($res === false) {
                        $message .= 'Error removing preformatted content.';
                        $error = true;
                    } else {
                        $wpf_preformatter['max_id'] = null;
                        update_option('_wpf_preformatter', $wpf_preformatter);
                        $message .= 'Preformatted content removed.';
                    }
                    break;
                case 'batch_start':
                case 'batch_reset':
                    list($results, $wpf_preformatter) = $this->_do_batch($wpf_preformatter, $_POST['wpf_action'] == 'batch_reset');
                    if ($results['error']) {
                        $message = 'Database error';
                        $error = true;
                    } else if ($results['complete']) {
                        $message = 'Batch preformatting completed.';
                    } else {
                        $message = 'Batch preformatting running: ' . $results['num'] . ' done, next batch size ' . $wpf_preformatter['batch_size'];
                    }
            }
        }
        ?>
        <script type="text/javascript">
        function batch_preformatting() {
            var batch_preformatting_complete = false;
            jQuery('#wpf_batch_preformatting_form').after('<h3>Batch Preformatting Results</h3><div id="batch_preformatting_results"></div>');
            while (!batch_preformatting_complete) {
                jQuery.ajax({
                    type: 'POST',
                    url: ajaxurl,
                    async: false,
                    data: {action:'wpf_batch_preformatting'},
                    success: function (response) {
                        batch_preformatting_complete = response['complete'];
                        jQuery('#batch_preformatting_results').append(
                            '<li>post ids ' + response['start'] + '-' + response['end'] + ':' + response['num'] + ' ' + (response['complete'] ? 'terminated' : 'still running') + '</li>'
                        );
                    }
                });
            }
        }
        </script>
        <?php
        echo "<div class=\"wrap\">\n";
        if ($message)
            echo '<div id="message" class="updated fade"><p>' . $message . ($error ? ' ' . $wpdb->last_error : '') . '</p></div>';
        echo "<h2>WP Frontman Preformatter Configuration</h2>\n";
        // enable or disable preformatting
        echo '<h3>Dynamic preformatting</h3>';
        if ($wpf_preformatter['enabled']) {
            echo '<p>Preformatting is enabled' . ($wpf_preformatter['relative_urls'] ? ' with media URL conversion to relative URLs.' : '.') . ' Click on the following button to disable it. Disabling preformatting will also clear formatted data.</p>';
            echo '<form action="" method="post"><input type="hidden" name="wpf_action" value="disable" /><input type="submit" class="button-primary" name="submit" value="Disable Dynamic Preformatting" /></form>';
        } else {
            echo '<p>Preformatting is disabled. Click on the following button to enable it.</p>';
            echo '<form action="" method="post"><input type="hidden" name="wpf_action" value="enable" /><input type="submit" class="button-primary" name="submit" value="Enable Dynamic Preformatting" /><input type="checkbox" ' . ($wpf_preformatter['relative_urls'] ? '$checked="checked" ' : '') . 'name="wpf_relative_urls" id="wpf_relative_urls" /><label for="wpf_relative_urls">Convert absolute media URLs to relative URLs</label></form>';
        }
        echo '<h3>Batch preformatting</h3>';
        if ($wpf_preformatter['batch_done']) {
            echo '<p>Old content has already been formatted. Click on the following button to start the batch preformatting process from scratch.</p>';
        } else {
            if ($wpf_preformatter['batch_running'])
                echo '<p>Old content is currently being formatted. Click on the following button process the next batch.</p>';
            else
                echo '<p>Old content has not been formatted yet. Click on the following button to start the batch preformatting process.</p>';
        }
        echo '<form action="" method="post" id="wpf_batch_preformatting_form">';
        echo '<input type="hidden" name="wpf_action" value="' . ($wpf_preformatter['batch_done'] ? 'batch_reset' : 'batch_start') . '" />';
        echo '<input type="submit" class="button-primary" name="submit" value="Preformat Old Posts" onclick="batch_preformatting(); return false;" />';
        echo '</form>';
        echo '<h3>Remove preformatted content</h3>';
        echo '<p>Click on the following button to remove any preformatted content fromall posts.</p>';
        echo '<form action="" method="post"><input type="hidden" name="wpf_action" value="remove" /><input type="submit" class="button-primary" name="submit" value="Remove Preformatted Content" /></form>';
        echo "</div>\n";
    }
    
    function ajax_preformatting() {
        $this->log("sending back ajax response");
        list($response, $wpf_preformatter) = $this->_do_batch();
        header('Content-Type: application/json');
        echo json_encode($response);
        die;
    }
    
    function _do_batch($wpf_preformatter=null, $reset=false) {
        global $wpdb;
        if (is_null($wpf_preformatter))
            $wpf_preformatter = $this->_get_option();
        $start = $reset ? 0 : $wpf_preformatter['max_id'];
        $start = is_null($start) ? 0 : $start;
        $end = $start + $wpf_preformatter['batch_size'];
        $num = 0;
        $error = null;
        $complete = $wpf_preformatter['batch_done'] = false;
        $wpf_preformatter['batch_running'] = true;
        $q = "select ID, post_content from {$wpdb->posts} where post_status='publish'";
        if ($wpf_preformatter['max_id'] && $_POST['wpf_action'] != 'batch_reset')
            $q .= " and ID > {$wpf_preformatter['max_id']}";
        $q .= " limit {$wpf_preformatter['batch_size']}";
        $run_start = time();
        $results = $wpdb->get_results($q, ARRAY_N);
        if (!is_array($results) || count($results) == 0) {
            if ($results == false && $wpdb->last_error) {
                $error = 'Database error';
            } else {
                $complete = true;
                $wpf_preformatter['batch_done'] = true;
                $wpf_preformatter['batch_running'] = false;
                update_option('_wpf_preformatter', $wpf_preformatter);
            }
        } else {
            $num = count($results);
            foreach ($results as $row) {
                $max_id = $row[0];
                $this->_preformat($max_id, $row[1], $wpf_preformatter['relative_urls']);
                $num++;
            }
            $time_spent = time() - $run_start;
            // we enforce a limit of five seconds spent preformatting
            if ($time_spent < 5)
                $wpf_preformatter['batch_size'] = $wpf_preformatter['batch_size'] * 2;
            if ($max_id > 0)
                $wpf_preformatter['max_id'] = $max_id;
            $max_id_in_db = $wpdb->get_var("select max(ID) from {$wpdb->posts} where post_status='publish'", 0, 0);
            if ($max_id_in_db && (int)$max_id_in_db <= $max_id) {
                $complete = true;
                $wpf_preformatter['batch_done'] = true;
                $wpf_preformatter['batch_running'] = false;
            }
            update_option('_wpf_preformatter', $wpf_preformatter);
        }
        return array(array(
            'start'=>$start, 'end'=>$end, 'num'=>$num, 'error'=>$error, 'complete'=>$complete
        ), $wpf_preformatter);
    }
    
    function log($s) {
        return;
        $f = fopen('/tmp/wpf.log', 'a+');
        fwrite($f, date("c") . " $s\n");
        fclose($f);
    }

}    


$preformatter =& new Preformatter();

?>