<?php
/**
 * The base configurations of the WordPress.
 *
 * This file has the following configurations: MySQL settings, Table Prefix,
 * Secret Keys, WordPress Language, and ABSPATH. You can find more information
 * by visiting {@link http://codex.wordpress.org/Editing_wp-config.php Editing
 * wp-config.php} Codex page. You can get the MySQL settings from your web host.
 *
 * This file is used by the wp-config.php creation script during the
 * installation. You don't have to use the web site, you can just copy this file
 * to "wp-config.php" and fill in the values.
 *
 * @package WordPress
 */

// ** MySQL settings - You can get this info from your web host ** //
/** The name of the database for WordPress */
define('DB_NAME', 'wpf');

/** MySQL database username */
define('DB_USER', 'ludo');

/** MySQL database password */
define('DB_PASSWORD', 'pippo');

/** MySQL hostname */
define('DB_HOST', 'localhost');

/** Database Charset to use in creating database tables. */
define('DB_CHARSET', 'utf8');

/** The Database Collate type. Don't change this if in doubt. */
define('DB_COLLATE', '');

/**#@+
 * Authentication Unique Keys and Salts.
 *
 * Change these to different unique phrases!
 * You can generate these using the {@link https://api.wordpress.org/secret-key/1.1/salt/ WordPress.org secret-key service}
 * You can change these at any point in time to invalidate all existing cookies. This will force all users to have to log in again.
 *
 * @since 2.6.0
 */
define('AUTH_KEY',         'Zj*jS 4&}i}xeXjfugcQ Q+`{sj-+}Qt<]jY ;izZmt|~4]EZ(ql;[gYsL!dE~=B');
define('SECURE_AUTH_KEY',  '4IY6(.eBhW[-o}6,(e]y;8+h<o7|p~K0Bw7lG0*/9Ck{RZTa**dElOg+ylnEGf/I');
define('LOGGED_IN_KEY',    'y*,5Ba}570tONyq-W3|8iv%JP]GVQ?IF.JJ,Trkj>n.do=ySLG=UcFDl--0;.M@e');
define('NONCE_KEY',        '-Jwm-=+R}XA2F1gWS+/y2xVR2cCW(>n2.U}sKFR,3-d-Pe-v}0)ebMEbRa.T(q%P');
define('AUTH_SALT',        ')Qb@Hqx-9j&:x7ZmOk}4@y41/Vrd|:}m1J<SSK9x| UB$uXI+EFsOIajm%`zKHt1');
define('SECURE_AUTH_SALT', '#0UsetXPKrMeIy2NYJ]M9p itjn>P7)K,R<-4XAe=-Q?$zY-kZ,7+1SJ)LO64:tk');
define('LOGGED_IN_SALT',   't;do+P%$c-GLxJ]9M!Mk|JEE+xGhRpJ5,6_GAWHUQMQL2A6C/hEj3/;<?@A]BPAN');
define('NONCE_SALT',       'M5`ju_DPV=Oy[vlg1?szPjH6tQ,ja/-upzZL]#~,r3VPU8>PK]J/b{b[ypm&r_@J');

/**#@-*/

/**
 * WordPress Database Table prefix.
 *
 * You can have multiple installations in one database if you give each a unique
 * prefix. Only numbers, letters, and underscores please!
 */
$table_prefix  = 'wp_';

/**
 * WordPress Localized Language, defaults to English.
 *
 * Change this to localize WordPress. A corresponding MO file for the chosen
 * language must be installed to wp-content/languages. For example, install
 * de_DE.mo to wp-content/languages and set WPLANG to 'de_DE' to enable German
 * language support.
 */
define('WPLANG', '');

/**
 * For developers: WordPress debugging mode.
 *
 * Change this to true to enable the display of notices during development.
 * It is strongly recommended that plugin and theme developers use WP_DEBUG
 * in their development environments.
 */
define('WP_DEBUG', false);

define('WP_ALLOW_MULTISITE', true);

define( 'MULTISITE', true );
define( 'SUBDOMAIN_INSTALL', false );
$base = '/';
define( 'DOMAIN_CURRENT_SITE', 'localhost' );
define( 'PATH_CURRENT_SITE', '/' );
define( 'SITE_ID_CURRENT_SITE', 1 );
define( 'BLOG_ID_CURRENT_SITE', 1 );

/* That's all, stop editing! Happy blogging. */

/** Absolute path to the WordPress directory. */
if ( !defined('ABSPATH') )
	define('ABSPATH', dirname(__FILE__) . '/');

/** Sets up WordPress vars and included files. */
require_once(ABSPATH . 'wp-settings.php');
