<?php
/*
Plugin Name: WP Frontman Network Settings
Plugin URI: http://wpfrontman.com/
Description: WP Frontman network settings
Version: 0.1
Author: Ludovico Magnocavallo
Author URI: http://qix.it/
*/


class WPFrontmanMU {
    
    var $db_version = 1;
    var $options_labels = array(
        //                                       section name       option label            input   help  default
        'wp_root'                   => array('Network Options', 'WP installation path', null, null, 'ABSPATH'),
        'cache_destination'         => array('Network Options', 'Frontend cache endpoint URL', 'text', null, null),
        'preformatter'              => array('Network Configuration', 'Enable preformatting for posts and pages', 'checkbox', 'Maintain plugins compatibility and speed up the frontend by storing a formatted copy of the content in <code>post_content_filtered</code>', true),
        'support_category_order'    => array('Network Configuration', 'My Category Order plugin installed', 'checkbox', 'Add support for the category order defined with the <a href="http://wordpress.org/extend/plugins/my-category-order/">My Category Order</a> plugin', false),
        'use_sendfile'              => array('Network Configuration', 'Use X-Sendfile for static content', 'checkbox', 'Refer to your HTTP/Fastcgi server documentation for details', false),
        'global_favicon'            => array('Network Defaults', 'Use a single favicon icon for all blogs', 'checkbox', 'The global favicon is in [wp root]/wp-content/ individual favicons in <code>wp-content/blogs.dir/[blog id]/</code>', false),
        'global_robots'             => array('Network Defaults', 'Use a single robots.txt file for all blogs', 'checkbox', 'The global robots.txt is in [wp root]/wp-content/ individual ones in <code>wp-content/blogs.dir/[blog id]/</code>', true),
        'categories_as_sets'        => array('Network Defaults', 'Parent categories include posts from children', 'checkbox', null, true),
        'wp_auth_key'               => array('Security Constants', 'WP auth key', null, null, 'AUTH_KEY'),
        'wp_auth_salt'              => array('Security Constants', 'WP auth salt', null, null, 'AUTH_SALT'),
        'wp_secret_key'             => array('Security Constants', 'WP secret key', null, null, 'SECRET_KEY'),
        'wp_secret_salt'            => array('Security Constants', 'WP secret salt', null, null, 'SECRET_SALT'),
        'wp_secure_auth_key'        => array('Security Constants', 'WP secure auth key', null, null, 'SECURE_AUTH_KEY'),
        'wp_secure_auth_salt'       => array('Security Constants', 'WP secure auth salt', null, null, 'SECURE_AUTH_SALT'),
        'wp_logged_in_key'          => array('Security Constants', 'WP logged in key', null, null, 'LOGGED_IN_KEY'),
        'wp_logged_in_salt'         => array('Security Constants', 'WP logged in salt', null, null, 'LOGGED_IN_SALT'),
        'wp_nonce_key'              => array('Security Constants', 'WP nonce key', null, null, 'NONCE_KEY'),
        'wp_nonce_salt'             => array('Security Constants', 'WP nonce salt', null, null, 'NONCE_SALT'),
    );
    var $options;
    var $message;
    // cache
    var $payloads = array();
    var $transitioned_posts = array();
    var $tracked_comments = array();
    var $deleted_comments = array();
    var $stored_permalinks = array();
    // preformatter
    var $home;
    var $relativize_port;
    var $relativize_regexp;

    function WPFrontmanMU() {
        // initialize defaults
        global $wp_default_secret_key;
        foreach ($this->options_labels as $k=>$v) {
            if (!is_null($v[2]))
                continue;
            $const_name = $v[4];
            $value = defined($const_name) ? constant($const_name) : null;
            if ($value == '' || $value == $wp_default_secret_key)
                $value = null;
            $this->options_labels[$k][4] = $value;
        }
        // activation hook, not really necessary
        register_activation_hook(implode(DIRECTORY_SEPARATOR, array_slice(explode(DIRECTORY_SEPARATOR, __FILE__), -1)), array($this, 'bootstrap'));
        // admin menu
        add_action('network_admin_menu', array(&$this, 'action_network_admin_menu'));
        // let's let ourselves known
        add_filter('admin_footer_text', array(&$this, 'filter_admin_footer_text'), 10, 1);
        // preformatter and cache
        add_action('save_post', array(&$this, 'action_save_post'), 10, 2);
        // cache post actions
        add_action('pre_post_update', array(&$this, 'action_pre_post_update'), 10, 1);
        add_action('transition_post_status', array(&$this, 'action_transition_status'), 10, 3);
        add_action('delete_post', array(&$this, 'action_delete_post'), 10, 1);
        // cache comment actions
        add_action('transition_comment_status', array(&$this, 'action_transition_comment_status'), 10, 3);
        add_action('wp_insert_comment', array(&$this, 'action_wp_insert_comment'), 10, 2);
        add_action('edit_comment', array(&$this, 'action_edit_comment'), 10, 1);
        add_action('delete_comment', array(&$this, 'action_delete_comment'), 10, 1);
        add_action('deleted_comment', array(&$this, 'action_deleted_comment'), 10, 1);
        // ajax action for cache regen
        add_action('wp_ajax_wpf_cache_regen', array(&$this, 'action_ajax_cache_regen'));
        // ajax action for batch preformatting
        add_action('wp_ajax_wpf_preformatter_batch', array(&$this, 'action_ajax_preformatter_batch'));
    }
    
    function get_defaults() {
        global $wpdb;
        $defaults = array_map(function ($v) { return $v[4]; }, $this->options_labels);
        $site_url = get_site_option('siteurl');
        $defaults['cache_destination'] = $site_url . (substr($site_url, -1) != '/' ? '/wpf_cache/' : 'wpf_cache/');
        $defaults['use_sendfile'] = defined('WPMU_SENDFILE') ? WPMU_SENDFILE : false;
        if (preg_match('/term_order/', implode(' ', $wpdb->get_row("show create table wp_terms", ARRAY_N))))
            $defaults['support_category_order'] = true;
        return $defaults;
    }
    
    function bootstrap($reset=false) {
        if (is_array($this->options))
            return;
        $options = $reset ? array() : get_site_option('wp_frontman', array());
        if (!array_key_exists('db_version', $options) || $options['db_version'] != $this->db_version) {
            $defaults = $this->get_defaults();
            foreach ($options as $k=>$v) {
                if (!array_key_exists($k, $defaults))
                    unset($options[$k]);
            }
            foreach ($defaults as $k=>$v) {
                if (!array_key_exists($k, $options))
                    $options[$k] = $v;
            }
            $options['db_version'] = $this->db_version;
            update_site_option('wp_frontman', $options);
            $this->message = $reset ? 'Options reset to defaults' : 'Options updated';
        }
        // sanity check
        $update = array();
        foreach ($this->options_labels as $k=>$v) {
            if ($v[2] === null && $options[$k] != $this->options_labels[$k][4]) {
                $options[$k] = $this->options_labels[$k][4];
                $update[] = $k;
            }
        }
        if ($update) {
            update_site_option('wp_frontman', $options);
            $this->message = "Options auto updated: '" . implode("', '", $update) . "'";
        }
        $this->options = $options;
    }
    
    function action_network_admin_menu() {
        add_submenu_page('settings.php', 'WP Frontman Network Settings', 'WP Frontman MU', 'manage_network_options', 'wp_frontman_mu', array(&$this, 'submenu_page'));
    }
    
    function filter_admin_footer_text($text) {
        return $text . ' &bull; MU Plugin for <a href="http://wp-frontman.com/">WP Frontman</a> running';
    }
    
    function submenu_page() {
        $reset = $_POST && array_key_exists('wpf_reset', $_POST) && $_POST['wpf_reset'];
        $this->bootstrap($reset);
        if ($_POST && !$reset) {
            $update = array();
            foreach ($this->options as $k=>$v) {
                $opt_type = $this->options_labels[$k][2];
                if (is_null($opt_type))
                    continue;
                if ($opt_type == 'checkbox') {
                    $v = array_key_exists($k, $_POST) && $_POST[$k] == 'on' ? true : false;
                } else if ($opt_type == 'text') {
                    if (!array_key_exists($k, $_POST))
                        continue;
                    $v = $_POST[$k];
                }
                if ($this->options[$k] == $v)
                    continue;
                $this->options[$k] = $v;
                $update[] = $k;
            }
            if ($update) {
                update_site_option('wp_frontman', $this->options);
                $this->message = "Updated '" . implode("', '", $update) . "'";
            }
        }
        echo "<div class=\"wrap\">\n<h2>WP Frontman Network Settings</h2>\n";
        if ($this->message)
            echo "<div id=\"message\" class=\"updated fade\"><p><strong>{$this->message}</strong></p></div>\n";
        echo "<form id=\"wpf_form\" method=\"POST\">\n";
        $current_section = null;
        foreach ($this->options_labels as $opt=>$opt_data) {
            list($section, $opt_label, $field_type, $help_text, $opt_default) = $opt_data;
            if ($section != $current_section) {
                if ($current_section !== null)
                    echo "</table>\n";
                echo "<table class=\"form-table\">\n<h3>$section</h3>\n";
                $current_section = $section;
            }
            echo "<tr>\n<th scope=\"row\" valign=\"top\"><label for=\"$opt\">$opt_label</label></th>\n<td valign=\"top\">\n";
            if ($field_type == 'text')
                echo "<input type=\"text\" id=\"$opt\" name=\"$opt\" value=\"{$this->options[$opt]}\" size=\"96\" />\n";
            else if ($field_type == 'checkbox')
                echo "<input type=\"checkbox\" id=\"$opt\" name=\"$opt\"" . ($this->options[$opt] ? ' checked="checked"' : '') . "\"  />\n";
            else if ($field_type === null)
                echo "<code id=\"$opt\">" . htmlspecialchars($this->options[$opt]) . "</code>\n";
            if ($help_text)
                echo "<br /><small style=\"font-style: italic;\">$help_text</small>\n";
            echo "</td>\n</tr>\n";
        }
        echo "</table>\n";
        echo "<p class=\"submit\"><input type=\"submit\" name=\"submit\" id=\"submit\" class=\"button-primary\" value=\"Save Changes\"></p>\n</form>\n";
        echo "<form id=\"wpf_form\" method=\"POST\">\n<input type=\"hidden\" name=\"wpf_reset\" value=\"1\" />\n";
        echo "<p class=\"submit\"><input type=\"submit\" name=\"submit\" id=\"submit\" class=\"button-primary\" value=\"Reset to Defaults\"></p>\n</form>\n";
        echo "</div>\n";
    }
    
    function action_save_post($post_id, $post) {
        $this->_action_save_post_preformatter($post_id, $post);
        $this->_action_save_post_cache($post_id, $post);
    }
    
    /**************************************************************************
     ****************************** cache methods *****************************
     **************************************************************************/
    
    /* post */
    
    function action_pre_post_update($post_id) {
        // only useful for storing the permalink of posts that will change status later
        $this->log("pre post update $post_id");
        $post = get_post($post_id);
        if ($post->post_status != 'publish')
            return;
        $this->stored_permalinks[$post_id] = get_permalink($post);
    }
    
    function _action_save_post_cache($post_id, $post) {
        $this->log("save post $post_id {$post->ID}");
        if ($post->post_status != 'publish' && !in_array($post_id, $this->transitioned_posts))
            return;
        $this->log("preparing post $post_id");
        $this->prepare_post($post_id, $post);
    }

    function action_transition_status($new, $old, $post) {
        $this->log("transition status $old $new {$post->ID}");
        if ($old == $new)
            return;
        if ($old != 'publish' && $new != 'publish')
            return;
        $this->log("flag this post for saving");
        $this->transitioned_posts[] = $post->ID;
    }

    function action_delete_post($post_id) {
        $this->log("delete post $post_id");
        $post = get_post($post_id);
        if (($post->post_type == 'post' || $post->post_type == 'page') && $post->post_status == 'publish')
            $this->prepare_post($post_id, $post);
    }
    
    /* comment actions */
    
    function action_transition_comment_status($new, $old, $comment) {
        if ($old == $new)
            return;
        if ($old != 'approved' && $new != 'approved')
            return;
        if (in_array($comment->comment_ID, $this->tracked_comments))
            return;
        $this->log("track this comment");
        $this->tracked_comments[] = $comment->comment_ID;
        $this->prepare_comment($comment->comment_ID, $comment);
    }
    
    function action_wp_insert_comment($id, $comment) {
        $this->log("wp_insert_comment $id " . var_export($comment, true));
        if (in_array($id, $this->tracked_comments))
            return;
        if (is_null($comment))
            $comment = get_comment($id);
        if (!in_array($comment->comment_approved, array(1, '1', 'approved')))
            return;
        $this->log("track this comment");
        $this->tracked_comments[] = $id;
        $this->prepare_comment($id, $comment);
    }
    
    function action_edit_comment($id) {
        $this->log("edit_comment $id");
        if (in_array($id, $this->tracked_comments))
            return;
        $comment = get_comment($id);
        if (!in_array($comment->comment_approved, array(1, '1', 'approved')))
            return;
        $this->log("track this comment");
        $this->tracked_comments[] = $id;
        $this->prepare_comment($id, $comment);
    }
    
    function action_delete_comment($id) {
        $this->log("delete_comment $id");
        if (in_array($id, $this->tracked_comments) || in_array($id, $this->deleted_comments))
            return;
        $comment = get_comment($id);
        if (!in_array($comment->comment_approved, array(1, '1', 'approved')))
            return;
        $this->log("store this comment");
        $this->deleted_comments[$id] = $comment;
    }
    
    function action_deleted_comment($id) {
        $this->log("deleted_comment $id");
        if (in_array($id, $this->tracked_comments))
            return;
        $comment = $this->deleted_comments[$id];
        if (!$comment)
            return;
        unset($this->deleted_comments[$id]);
        $this->log("track this comment");
        $this->tracked_comments[] = $id;
        $this->prepare_comment($id, $comment);
    }
    
    /* ajax action to send a global timestamp */
    function action_ajax_cache_regen() {
        global $blog_id;
        check_ajax_referer('wp_frontman', 'security');
        $this->bootstrap();
        $timestamp = time();
        $value = serialize(array());
        $this->log("sender using salt {$this->options['wp_logged_in_salt']}");
        $payload = "$blog_id|regen|$timestamp|" . hash('sha256', "{$this->options['wp_logged_in_salt']}${blog_id}regen$value$timestamp") . "|$value";
        $this->log("sending payload: $payload");
        $res = $this->_send_payloads($payload);
        header('Content-Type: text/plain');
        die($res ? "FAIL $res" : 'OK');
    }
    
    /* prepare payloads */
    
    function prepare_comment($comment_id, $comment=null) {
        global $blog_id;
        
        $this->bootstrap();
        
        if (!$this->options['cache_destination'] || !$this->options['wp_logged_in_salt'])
            return;
        
        $this->log("appending payload for comment $comment_id");
        
        if (!$comment)
            $comment = get_comment($comment_id);
        
        $post = get_post($comment->comment_post_ID);
        $permalink = get_permalink($post);
        //$author = get_userdata($post->post_author);
        
        $value = array(
            'id'                => $comment_id,
            'post_id'           => $comment->comment_post_ID,
            'post_type'         => $post->post_type,
            'status'            => $post->post_status,
            'slug'              => $post->post_name,
            'date'              => $post->post_date,
            //'author_id'         => $post->post_author,
            //'author_nicename'   => $author->user_nicename,
            'path'              => parse_url($permalink, PHP_URL_PATH)
        );

        $value = serialize($value);
        
        $timestamp = time();
        $this->payloads[] = "$blog_id|comment|$timestamp|" . hash('sha256', "{$this->options['wp_logged_in_salt']}${blog_id}comment$value$timestamp") . "|$value";
    }

    function prepare_post($post_id, $post) {
        global $blog_id;
        
        $this->bootstrap();
        
        if (!$this->options['cache_destination'] || !$this->options['wp_logged_in_salt'])
            return;
        
        $this->log("appending payload for post $post_id");
        
        $key = $post->post_type;

        if (isset($this->stored_permalinks[$post->ID]))
            $permalink = $this->stored_permalinks[$post->ID];
        else
            $permalink = get_permalink($post);
        
        $author = get_userdata($post->post_author);
        
        $value = array(
            'id'                => $post->ID,
            'post_type'         => $post->post_type,
            'status'            => $post->post_status,
            'slug'              => $post->post_name,
            'date'              => $post->post_date,
            'author_id'         => $post->post_author,
            'author_nicename'   => $author->user_nicename,
            //'path'              => parse_url($permalink, PHP_URL_PATH),
            'taxonomy'          => array()
        );
        foreach (wp_get_object_terms($post->ID, array('category', 'post_tag')) as $t) {
            #$t->permalink = get_term_link($t, $t->taxonomy);
            $value['taxonomy'][] = array(
                id=>$t->term_taxonomy_id,
                taxonomy=>$t->taxonomy
                //path=>parse_url(get_term_link($t, $t->taxonomy), PHP_URL_PATH)
            );
        }
        //$this->log(var_export($value, true));
        $value = serialize($value);
        
        $timestamp = time();
        $this->payloads[] = "$blog_id|$key|$timestamp|" . hash('sha256', "{$this->options['wp_logged_in_salt']}$blog_id$key$value$timestamp") . "|$value";
    }
    
    function _send_payloads($payload=null) {
        
        if (is_null($payload) && !$this->payloads)
            return;
        
        $this->bootstrap();
        
        $this->log("sending " . ($payload ? "1 payload" : count($this->payloads) . " payloads"));

        $ch = curl_init($this->options['cache_destination']);
        
        $payload = $payload ? $payload : implode("\n", $this->payloads);

        $this->log($payload);
        
        curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, array('Expect:'));
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        //curl_setopt($ch, CURLOPT_POSTFIELDSIZE, strlen($payload));
        //curl_setopt($ch, CURLOPT_HTTPHEADER, array('Content-Type'=>'text/plain'));
        
        $res = curl_exec($ch);
    
        $errno = curl_errno($ch);
        $info = curl_getinfo($ch);
    
        if (!$res || $errno || $info['http_code'] != 200 || $res != 'OK') {
            $message = "error posting to {$this->options['cache_destination']} ";
            if ($errno)
                $message .= "curl error " . curl_error($ch) . " ";
            if ($info)
                $message .= "HTTP status {$info['http_code']} ";
            //if ($res)
            //    $message .= " response $res";
            $this->log("failure\npayload:\n$payload\nmessage:\n$message\nresponse:\n$res\n");
            return $message;
        }
        
        $this->log("success {$info['http_code']} $res");
        curl_close($ch);
        
    }
    
    function __destruct() {
        $this->log("sending payloads");
        $this->_send_payloads();
    }

    /**************************************************************************
     ************************** preformatter methods **************************
     **************************************************************************/
    
    function _action_save_post_preformatter($post_id, $post) {
        if ($post->post_type != 'post' && $post->post_type != 'page')
            return;
        global $wpdb;
        $this->bootstrap();
        if (!$this->options['preformatter']) {
            if ($post->post_content_filtered)
                $wpdb->query("UPDATE $wpdb->posts SET post_content_filtered = '' WHERE ID = '$post_id'");
            return;
        }
        if ($post->post_status != 'publish' && $post->post_status != 'draft') {
            $wpdb->query("UPDATE $wpdb->posts SET post_content_filtered = '' WHERE ID = '$post_id'");
            return;
        }
        $options = get_option('wp_frontman', array());
        $this->_preformat($post_id, $post->post_content, !array_key_exists('preformatter', $options) || $options['preformatter']['relative_urls']);
        $this->log("preformatted");
    }
    
    /* ajax action for batch preformatting */
    function action_ajax_preformatter_batch() {
        
        global $wpdb;
        check_ajax_referer('wp_frontman', 'security');
        $this->bootstrap();
        $blog_options = get_option('wp_frontman', array());
        $options =& $blog_options['preformatter'];

        $reset = array_key_exists('reset', $_POST) ? (bool)$_POST['reset'] : false;
        if ($reset) {
            $options['max_id'] = 0;
            $options['batch_done'] = false;
        }
        $options['batch_running'] = true;
        $start = $reset ? 0 : $options['max_id'];
        $num = 0;
        $error = null;
        $complete = $options['batch_done'] = false;
        $options['batch_running'] = true;
        
        $q = "select ID, post_content from {$wpdb->posts} where post_status='publish' and ID > $start limit {$options['batch_size']}";
        $run_start = time();
        $results = $wpdb->get_results($q, ARRAY_N);
        if (!is_array($results) || count($results) == 0) {
            if ($results == false && $wpdb->last_error) {
                $error = "Database error: {$wpdb->last_error}, query: $q";
            } else {
                $complete = true;
                $options['batch_done'] = true;
                $options['batch_running'] = false;
                $options['max_id'] = 0;
                update_option('wp_frontman', $blog_options);
            }
        } else {
            $num = 0;
            foreach ($results as $row) {
                $max_id = $row[0];
                $this->_preformat($max_id, $row[1], $options['relative_urls']);
                $num++;
            }
            $time_spent = time() - $run_start;
            // we enforce a limit of five seconds spent preformatting
            //if ($time_spent < 5)
            //    $options['_current_batch_size'] = $options['batch_size'] * 2;
                
            if ($max_id > 0)
                $options['max_id'] = $max_id;
            $max_id_in_db = $wpdb->get_var("select max(ID) from {$wpdb->posts} where post_status='publish'", 0, 0);
            if ($max_id_in_db && (int)$max_id_in_db <= $max_id) {
                $complete = true;
                $options['batch_done'] = true;
                $options['batch_running'] = false;
                $options['max_id'] = 0;
            }
            update_option('wp_frontman', $blog_options);
        }
        header('Content-Type: application/json');
        echo json_encode(array(
            'start'=>$start, 'num'=>$num, 'time'=>$time_spent, 'error'=>$error, 'complete'=>$complete
        ));
        die;
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
    
    function _relativize($content) {
        if (is_null($this->regexp)) {
            if (is_null($this->home))
                $this->home = get_option('home');
            if (is_null($this->home))
                return $content;
            $t = parse_url($this->home);
            $this->regexp = '#<(?:img|a)\s+[^>]*[src|href]=\\\?["\'](' . $t['scheme'] . '://' . $t['host'] . '[^"\'\\\]+)#i';
            $this->relativize_port = isset($t['port']) ? $t['port'] : null;
        }
        preg_match_all($this->regexp, $content, $matches);
        if (isset($matches[1])) {
            foreach ($matches[1] as $url) {
                $t = parse_url($url);
                if (isset($t['port']) && $t['port'] != $this->relativize_port)
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

    function log($s) {
        $f = fopen('/tmp/wpf.log', 'a+');
        fwrite($f, date("c") . " $s\n");
        fclose($f);
    }

}


if (function_exists('is_admin') && is_admin()) {
    $wpf =& new WPFrontmanMU();
}

?>
