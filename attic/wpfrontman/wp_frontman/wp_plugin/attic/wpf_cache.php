<?php
/*
Plugin Name: WP Frontman Cache
Plugin URI: http://wpfrontman.com/
Description: Sends objects timestamps as key/value pairs via HTTP to WP Frontman
Version: 0.1
Author: Ludovico Magnocavallo
Author URI: http://qix.it/
*/

//error_reporting(E_ALL|E_NOTICE);


class WPFCache {
    
    var $payloads = array();
    var $transitioned_posts = array();
    var $tracked_comments = array();
    var $deleted_comments = array();
    var $stored_permalinks = array();

    function WPFCache() {
        $this->log("------------------------------------------------------------");
        $this->log("initializing");
        
        // base attributes
        $url = get_option('wpf_cache_destination', null);
        if (!$url) {
            global $blog_id;
            $url = get_home_url($blog_id, '/wpf_cache/');
        }
        $this->url = $url;
        $this->salt = defined('LOGGED_IN_SALT') ? LOGGED_IN_SALT : get_site_option('logged_in_salt');
        if (empty($this->salt)) {
            $this->salt = wp_generate_password(64, true, true);
            update_site_option('logged_in_salt', $this->salt);
        }
        // admin actions
        add_action('admin_menu', array(&$this, 'action_submenu'));
        // post actions
        add_action('save_post', array(&$this, 'action_save_post'), 10, 2);
        add_action('pre_post_update', array(&$this, 'action_pre_post_update'), 10, 1);
        add_action('transition_post_status', array(&$this, 'action_transition_status'), 10, 3);
        add_action('delete_post', array(&$this, 'action_delete_post'), 10, 1);
        // comment actions
        add_action('transition_comment_status', array(&$this, 'action_transition_comment_status'), 10, 3);
        add_action('wp_insert_comment', array(&$this, 'action_wp_insert_comment'), 10, 2);
        add_action('edit_comment', array(&$this, 'action_edit_comment'), 10, 1);
        add_action('delete_comment', array(&$this, 'action_delete_comment'), 10, 1);
        add_action('deleted_comment', array(&$this, 'action_deleted_comment'), 10, 1);
        $this->log("initialization completed");
    }
    
    /* admin actions */
    
    function action_submenu() {
        if (function_exists('add_submenu_page')) {
            add_submenu_page(
                'plugins.php',
                'WPF Cache Configuration', 'WPF Cache',
                'activate_plugins', 'wpf_cache',
                array(&$this, 'submenu_configuration')
            );
        }
        if (!get_option('wpf_cache_destination', null) && !isset($_POST['wpf_cache_destination'])) {
            global $blog_id;
            function wpf_cache_warning() {
                echo '<div class="updated fade"><p><strong>No <a href="' . get_admin_url($blog_id, '/plugins.php?page=wpf_cache') . '">destination set</a> for WPF Cache.</p></div>';
            }
            add_action('admin_notices', 'wpf_cache_warning');
        }
    }
    
    /* post actions */
    
    function action_pre_post_update($post_id) {
        // only useful for storing the permalink of posts that will change status later
        $this->log("pre post update $post_id");
        $post = get_post($post_id);
        if ($post->post_status != 'publish')
            return;
        $this->stored_permalinks[$post_id] = get_permalink($post);
    }
    
    function action_save_post($post_id, $post) {
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
        // we need to register this post in the cache, set a flag for post_save
        // with the post permalink so that we can use it for non-published posts
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
        $this->log("transition comment status $old $new {$comment->post_id}");
        if ($old == $new)
            return;
        if ($old != 'approved' && $new != 'approved')
            return;
        // we need to register this post in the cache, set a flag for post_save
        // with the post permalink so that we can use it for non-published posts
        if (in_array($comment->comment_ID, $this->tracked_comments))
            return;
        $this->log("track this comment");
        $this->tracked_comments[] = $comment->comment_ID;
        $this->prepare_comment($comment->comment_ID, $comment);
    }
    
    /*
        edit_comment -> track only for approved comments
        transition_comment_status -> track only for transitions from/to approved, and for comments not deleted
        delete_comment -> track only for approved comments
        wp_insert_comment -> track only for approved comments
     */
    
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
    
    /* prepare payloads */
    
    function prepare_comment($comment_id, $comment=null) {
        global $blog_id;
        
        if (!$this->url)
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
        $this->payloads[] = "$blog_id|comment|$timestamp|" . hash('sha256', "{$this->salt}${blog_id}comment$value$timestamp") . "|$value";
    }

    function prepare_post($post_id, $post) {
        global $blog_id;
        if (!$this->url)
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
        $this->payloads[] = "$blog_id|$key|$timestamp|" . hash('sha256', "{$this->salt}$blog_id$key$value$timestamp") . "|$value";
    }
    
    function __destruct() {
        
        if (!$this->payloads)
            return;
        
        $this->log("sending " . count($this->payloads) . " payloads");
        
        $ch = curl_init($this->url);
        
        $payload = implode("\n", $this->payloads);
        
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
            $message = "error posting to {$this->url} ";
            if ($errno)
                $message .= "curl error " . curl_error($ch) . " ";
            if ($info)
                $message .= "HTTP status {$info['http_code']} ";
            if ($res)
                $message .= " response $res";
            $this->log("failure\npayload:\n$payload\nmessage:\n$message");
            return;
        }
        
        $this->log("success {$info['http_code']} $res");
        curl_close($ch);
    }
        
    function submenu_configuration() {
        if (isset($_POST['wpf_cache_destination'])) {
            update_option('wpf_cache_destination', $_POST['wpf_cache_destination']);
            $this->url = $_POST['wpf_cache_destination'];
        }
        echo "<div class=\"wrap\">\n";
        echo "<h2>WPF Cache Configuration</h2>\n";
        echo "<form action=\"\" method=\"post\" id=\"wpf_cache\">\n";
        echo "<p>";
        echo '<label for="id_wpf_cache_destination">URL to submit cache timestamps to</label><br />';
        echo '<input type="text" id="wpf_cache_destination" name="wpf_cache_destination" value="' . $this->url . '" style="width: 320px;" />';
        echo "</p><p>";
        echo "<input type=\"submit\" name=\"submit\" value=\"Save\" />\n";
        echo "</p>";
        echo "</form>\n";
        echo "</div>\n";
    }

    function log($s) {
        return;
        $f = fopen('/tmp/wpf.log', 'a+');
        fwrite($f, date("c") . " $s\n");
        fclose($f);
    }

}
    

if (!isset($wp_cache_plugin))
    $wpf_cache_plugin =& new WPFCache();


?>
