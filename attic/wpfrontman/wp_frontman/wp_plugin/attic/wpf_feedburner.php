<?php
/*
Plugin Name: WP Frontman Feedburner Redirection
Plugin URI: http://wpfrontman.com/
Description: Redirects specific URLs to a different URL if the user agent is not Feedburner's
Version: 0.1
Author: Ludovico Magnocavallo
Author URI: http://qix.it/
*/


add_action('admin_menu', 'feedburner_config');

function feedburner_config() {
	global $wpdb;
	if (function_exists('add_submenu_page')) {
		add_submenu_page(
            'plugins.php',
			'WPF Feedburner Configuration', 'WPF Feedburner',
			8, 'feedburner', 'feedburner_page'
        );
    }
}

function feedburner_page() {
    echo "<div class=\"wrap\">\n";
    $options = get_option('wpf_feedburner');
	if (isset($_POST['submit'])) {
		check_admin_referer();
        foreach (array('url'=>null, 'url_requests'=>"feed/atom\nfeed/rss2\n", 'comments_url'=>null, 'comments_url_requests'=>"") as $k=>$v)
            $options[$k] = isset($_POST[$k]) ? $_POST[$k] : $v;
        update_option('wpf_feedburner', $options);
        echo "<div id='message' class='updated fade'><p>Configuration updated</p></div>\n";
    }
    echo "<h2>Feedburner Configuration</h2>\n";
    echo '<form action="" method="post" id="feedburner">';
    echo '
        <h3><label for="url">Main feed URL</label></h3>
        <p><input id="url" name="url" type="text" size="75" maxlength="200" value="' . $options['url'] . '" /></p>
        <h3><label for="url_requests">Main feed requests</label></h3>
        <p><textarea id="url_requests" name="url_requests" cols="75" rows="5">' . $options['url_requests'] . '</textarea></p>
    ';
    echo '
        <h3><label for="comments_url">Comments feed URL</label></h3>
        <p><input id="comments_url" name="comments_url" type="text" size="75" maxlength="200" value="' . $options['comments_url'] . '" /></p>
        <h3><label for="comments_url_requests">Comments feed requests</label></h3>
        <p><textarea id="comments_url_requests" name="comments_url_requests" cols="75" rows="5">' . $options['comments_url_requests'] . '</textarea></p>
    ';
    echo '
        <p class="submit" style="text-align: left"><input type="submit" name="submit" value="Save &raquo;" /></p>
        </form>
         </div>
     ';
}

function check_redirect(&$wp) {
    $request = $wp->request;
    if (!$request)
        return;
    if (isset($_SERVER['HTTP_USER_AGENT']) && preg_match('#feedburner.*feedburner.com#i', $_SERVER['HTTP_USER_AGENT']))
        return;
    $o = get_option('wpf_feedburner');
    if (!is_array($o))
        return;
    foreach (array('url', 'comments_url') as $a) {
        $u = $o[$a];
        $r = $o["${a}_requests"];
        if (!$u || !$r)
            return;
        $r = explode("\n", $r);
        foreach ($r as $req) {
            $req = trim($req);
            if ($request != $req)
                continue;
            header("Location: $u");
            exit(0);
        }
    }
}

add_action('parse_request', 'check_redirect');

?>