import re
import hmac

from collections import namedtuple
from threading import local
from hashlib import md5
from urlparse import urljoin, urlsplit, urlunsplit, SplitResult

from django.conf import settings
from django.db import connection

from wp_frontman.lib.external.phpserialize import loads as php_unserialize


DB_PREFIX = getattr(settings, 'WPF_DB_PREFIX', 'wp_')
WP_DEFAULT_BLOG_ID = getattr(settings, 'WPF_WP_DEFAULT_BLOG', 1)
OPTIONS_MODULE = getattr(settings, 'WPF_OPTIONS_MODULE', 'wpf_blogs')


def strtobool(s):
    """Damn WP and its habit of using strings instead of ints for bools in MySQL"""
    try:
        i = int(s)
    except (TypeError, ValueError):
        return s
    return bool(i)


# TODO: optimize site and blog options access with static modules
class Site(object):
    
    meta_keys = dict(
        dm_hash=str, admin_email=str, admin_user_id=int,
        registration=lambda v: False if v == 'none' else True,
        registrationnotification=lambda v: True if v == 'yes' else False,
        site_admins=php_unserialize, site_name=str, siteurl=str,
        subdomain_install=strtobool, wp_frontman=php_unserialize,
        auth_salt=str
    )
    wpf_options = dict(
        wp_root                 = getattr(settings, 'WPF_WP_ROOT', None),
        wp_auth_key             = getattr(settings, 'WPF_WP_AUTH_KEY', None),
        wp_auth_salt            = getattr(settings, 'WPF_WP_AUTH_SALT', None),
        wp_secret_key           = getattr(settings, 'WPF_WP_SECRET_KEY', None),
        wp_secret_salt          = getattr(settings, 'WPF_WP_SECRET_SALT', None),
        wp_secure_auth_key      = getattr(settings, 'WPF_WP_SECURE_AUTH_KEY', None),
        wp_secure_auth_salt     = getattr(settings, 'WPF_WP_SECURE_AUTH_SALT', None),
        wp_logged_in_key        = getattr(settings, 'WPF_WP_LOGGED_IN_KEY', None),
        wp_logged_in_salt       = getattr(settings, 'WPF_WP_LOGGED_IN_SALT', None),
        wp_nonce_key            = getattr(settings, 'WPF_WP_NONCE_KEY', None),
        wp_nonce_salt           = getattr(settings, 'WPF_WP_NONCE_SALT', None),
        support_category_order  = getattr(settings, 'WPF_SUPPORT_CATEGORY_ORDER', None),
        use_sendfile            = getattr(settings, 'WPF_SENDFILE', None),
        categories_as_sets      = getattr(settings, 'WPF_CATEGORIES_AS_SETS', None),
        global_favicon          = getattr(settings, 'WPF_GLOBAL_FAVICON', None),
        global_robots           = getattr(settings, 'WPF_GLOBAL_ROBOTS', None),
    )
    _wp_salts = dict()

    def __init__(self, site_id):
        self.site_id = 1
        self.meta = self.get_meta(site_id)
        wpf_options = self.wpf_options.copy()
        if 'wp_frontman' in self.meta:
            for k, v in self.meta['wp_frontman'].items():
                wpf_options[k] = wpf_options.get(k) or v
            del self.meta['wp_frontman']
        self.wpf_options = wpf_options
        # shortcut the hashed siteurl meta value, so as to save one md5 call for each request
        self.siteurl_hash = md5(self.siteurl).hexdigest()
        self.blogs = self.get_blogs(site_id)
        self.blog_paths = dict((b.path.replace('/', ''), b.blog_id) for b in self.blogs.values())
        self.blog_domains = dict((b.domain, b.blog_id) for b in self.blogs.values())
        self.blog_redirects = dict((b.secondary_domain, b.domain) for b in self.blogs.values() if b.secondary_domain)
        
    def __getattr__(self, name):
        if name in self.wpf_options:
            return self.wpf_options[name]
        if name in self.meta:
            return self.meta[name]
        raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, name))

    def wp_salt(self, scheme='auth'):
        secret_key = self.wp_secret_key or ''
        if not scheme in self._wp_salts:
            if scheme == 'auth':
                secret_key = self.wp_auth_key or secret_key
                salt = self.wp_auth_salt or None
                salt = salt or self.wp_secret_salt
                salt = salt or self.auth_salt
            elif scheme == 'secure_auth':
                secret_key = self.wp_secure_auth_key or secret_key
                salt = self.wp_secure_auth_salt or None
            elif scheme == 'logged_in':
                secret_key = self.wp_logged_in_key or secret_key
                salt = self.wp_logged_in_salt or None
            elif scheme == 'nonce':
                secret_key = self.wp_nonce_key or secret_key
                salt = self.wp_nonce_salt or None
            else:
                salt = hmac.new(secret_key, scheme).hexdigest()
            if salt is None or secret_key is None:
                raise ValueError("Either the secret key or the salt for scheme '%s' are undefined." % scheme)
            self._wp_salts[scheme] = secret_key + salt
        return self._wp_salts[scheme]
    
    def wp_hash(self, data, scheme='auth'):
        return hmac.new(self.wp_salt(scheme), data).hexdigest()
    
    def blog_for_path(self, path):
        # WP enforces a single path token for blogs in subdirectory mode,
        # but only when creating a new site; as often happens with WP,
        # administrators can shoot themselves on the foot by changing the
        # path to an invalid one from the site editing page
        tokens = [t for t in path.split('/') if t]
        if not tokens:
            blog_id = WP_DEFAULT_BLOG_ID
        else:
            blog_id = self.blog_paths.get(tokens[0], WP_DEFAULT_BLOG_ID)
        return Blog.factory(blog_id)
            
    def blog_for_domain(self, domain):
        if domain in self.blog_redirects:
            raise ValueError(self.blog_redirects[domain])
        blog_id = self.blog_domains.get(domain, WP_DEFAULT_BLOG_ID)
        return Blog.factory(blog_id)
        
    @classmethod
    def get_blogs(cls, site_id, force=False):
        blogs = dict()
        if OPTIONS_MODULE and not force:
            try:
                mod = __import__('.'.join((OPTIONS_MODULE, 'blogs')))
            except ImportError:
                pass
            else:
                blogs = getattr(mod, 'blogs', None)
                if blogs:
                    return blogs
        cursor = connection.cursor()
        if cursor.execute("show tables like '%sdomain_mapping'" % DB_PREFIX):
            cursor.execute("""
                select b.blog_id, if(dm.active=1, dm.domain, b.domain) as domain, if(dm.active=1, b.domain, NULL) as secondary_domain, b.path, b.archived, b.lang_id
                from %sblogs b
                left join %sdomain_mapping dm on dm.blog_id=b.blog_id
                where site_id=%%s and deleted=0
            """ % (DB_PREFIX, DB_PREFIX), (site_id,))
        else:
            cursor.execute("""
                select blog_id, domain, NULL as secondary_domain, path, archived, lang_id
                from %sblogs
                where site_id=%%s and deleted=0
            """ % DB_PREFIX, (site_id,))
        SiteBlog = namedtuple('SiteBlog', [f[0] for f in cursor.description])
        return dict((r[0], SiteBlog(*r)) for r in cursor.fetchall())
        
    @classmethod
    def get_meta(cls, site_id, force=False):
        meta = dict()
        if OPTIONS_MODULE and not force:
            try:
                mod = __import__('.'.join((OPTIONS_MODULE, 'site_options')))
            except ImportError:
                pass
            else:
                return dict((k, getattr(mod, k)) for k in dir(mod) if k in cls.meta_keys)
        cursor = connection.cursor()
        cursor.execute("select meta_key, meta_value from %ssitemeta where site_id=%%s and left(meta_key, 1) != '_'" % DB_PREFIX, (site_id,))
        for k, v in cursor.fetchall():
            if not k in cls.meta_keys:
                continue
            meta[k] = cls.meta_keys[k](v)
        meta['siteurl_tokens'] = meta['pingback_url'] = None
        if 'siteurl' in meta:
            t = urlsplit(meta['siteurl'])
            meta['siteurl_tokens'] = t
            if len(t.path) > 1 and not t.path.endswith('/'):
                path = t.path + '/'
            elif not t.path:
                path = '/'
            else:
                path = t.path
            meta['pingback_url'] = urlunsplit((t.scheme, t.netloc, t.path + 'xmlrpc.php', '', ''))
        return meta


class Blog(object):
    
    wp_permalink_tokens = dict(
        year='[0-9]{4}', monthnum='[0-9]{1,2}', day='[0-9]{1,2}', hour='[0-9]{1,2}',
        minute='[0-9]{1,2}', second='[0-9]{1,2}', postname='[^/]+', post_id='[0-9]+',
        category='.+?', tag='.+?', author='[^/]+', pagename='[^/]+?', search='.+'
    )
    
    wp_permalink_map = dict(
        monthnum='month', postname='slug', post_id='id', search='q'
    )

    wp_permalink_re = re.compile(r'%([a-z_]+)%')
    
    wp_options = dict(
        admin_email=str, avatar_default=str, avatar_rating=str, blacklist_keys=str,
        blog_public=strtobool, blogdescription=str, blogname=str, category_base=str,
        category_children=php_unserialize, comment_max_links=int, comment_moderation=bool,
        comment_order=str, comment_registration=strtobool, comment_whitelist=strtobool,
        comments_notify=strtobool, comments_per_page=int, current_theme=str, date_format=str,
        default_category=int, default_comment_status=str,
        default_comments_page=dict(newest='last', oldest='first').get,
        default_link_category=int, default_ping_status=str, default_pingback_flag=strtobool,
        fileupload_url=str, home=str, html_type=str, language=str, links_recently_updated_time=int,
        links_updated_date_format=str, mailserver_login=str, mailserver_pass=str,
        mailserver_port=int, mailserver_url=str, moderation_notify=strtobool,
        page_comments=strtobool, permalink_structure=str, ping_sites=str, post_count=str,
        posts_per_page=int, posts_per_rss=int, require_name_email=strtobool,
        rewrite_rules=php_unserialize, rss_language=str, rss_use_excerpt=bool,
        show_avatars=strtobool, siteurl=str, start_of_week=int, tag_base=str, template=str,
        thread_comments=strtobool, thread_comments_depth=int, time_format=str, timezone_string=str,
        upload_path=str, upload_url_path=str, use_trackback=strtobool, WPLANG=str, wp_user_roles=php_unserialize,
        wordpress_api_key=str, defensio_key=str, wp_frontman=php_unserialize,
    )
    skip_unless_force = (
        'category_children', 'rewrite_rules', 'links_recently_updated_time', 'links_updated_date_format',
        'default_pingback_flag', 'mailserver_login', 'mailserver_pass', 'mailserver_port',
        'mailserver_url', 'upload_path', 'upload_url_path', 'use_trackback'
    )
    
    site = Site(getattr(settings, 'WPF_WP_SITE_ID', 1))
    local_data = local()
    _cache = dict()
    
    @classmethod
    def get_active_db_prefix(cls):
        return cls.local_data.active_blog.db_prefix
    
    @classmethod
    def get_active(cls):
        return cls.local_data.active_blog
    
    @classmethod
    def set_active(cls, obj):
        if isinstance(obj, int):
            cls.factory(obj)
        else:
            cls.local_data.active_blog = obj
        
    @classmethod
    def reset_active(cls):
        cls.local_data.active_blog = None
        
    @classmethod
    def default_active(cls):
        cls.factory(WP_DEFAULT_BLOG_ID)
        
    @classmethod
    def factory(cls, blog_id, set_active=True):
        if blog_id in cls._cache:
            obj = cls._cache[blog_id]
        else:
            blog_data = cls.site.blogs.get(blog_id)
            if not blog_data:
                raise ValueError("Blog with id '%s' not found." % blog_id)
            obj = cls(*blog_data)
            cls._cache[blog_id] = obj
        if set_active:
            cls.local_data.active_blog = obj
        return obj
    
    @classmethod
    def get_blogs(cls):
        return [cls.factory(b, set_active=False) for b in cls.site.blogs]

    def __init__(self, blog_id, domain, secondary_domain, path, archived, lang_id):
        self.blog_id = blog_id
        self.domain = domain
        self.secondary_domain = secondary_domain
        self.path = path
        self.archived = archived
        self.lang_id = lang_id
        self.options = self.get_options(blog_id)
        self._cache = dict()
        
    @property
    def cache(self):
        return self._cache
        
    @property
    def urlrule_path(self):
        if not self.path:
            return ''
        path = self.path[1:] if self.path[0] == '/' else self.path
        path = path if path.endswith('/') else path + '/'
        return path if path != '/' else ''
    
    @property
    def is_default(self):
        return self.blog_id == WP_DEFAULT_BLOG_ID
        
    @property
    def comments_check_wp_user(self):
        return self.comment_registration or self.site.registration
    
    @property
    def db_prefix(self):
        return DB_PREFIX if self.blog_id == 1 else "%s%s_" % (DB_PREFIX, self.blog_id)
    
    @property
    def urlconf(self):
        return '%s.urls_%s' % (OPTIONS_MODULE, self.blog_id)
        
    def get_taxonomy_attributes(self, taxonomy):
        custom_taxonomies = self.options.get('wp_frontman', dict()).get('custom_taxonomies', dict())
        return custom_taxonomies.get(taxonomy)
    
    def __getattr__(self, name):
        if name in self.options:
            return self.options[name]
        raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, name))
    
    def get_options(self, blog_id, force=False):
        options = dict()
        if OPTIONS_MODULE and not force:
            try:
                mod = __import__('.'.join((OPTIONS_MODULE, 'blog_%s_options' % blog_id)))
            except ImportError:
                pass
            else:
                return dict((k, getattr(mod, k)) for k in dir(mod) if k in self.meta_keys)
        db_prefix = DB_PREFIX if blog_id == 1 else "%s%s_" % (DB_PREFIX, blog_id)
        cursor = connection.cursor()
        cursor.execute("select option_name, option_value from %soptions where autoload='yes' order by option_name" % db_prefix)
        for k, v in cursor.fetchall():
            if not force and k in self.skip_unless_force:
                continue
            func = self.wp_options.get(k)
            if func is None:
                continue
            try:
                options[k] = func(v)
            except ValueError, e:
                print k
                raise
        if not options.get('permalink_structure'):
            raise ImproperlyConfigured("No 'permalink_structure' option found in options for blog '%s'" % blog_id)
        permalink_structure = options.get('permalink_structure')
        if permalink_structure.startswith('/index.php'):
            permalink_structure = permalink_structure[10:]
        if permalink_structure.startswith('/'):
            permalink_structure = permalink_structure[1:]
        ps  = permalink_structure
        permalink_tokens = list()
        scanner = self.wp_permalink_re.scanner(ps)
        ps_tokens = list()
        start = 0
        while True:
            m = scanner.search()
            if not m:
                break
            ps_tokens.append(re.escape(ps[start:m.start()]))
            permalink_tokens.append(self.wp_permalink_map.get(m.group(1), m.group(1)))
            ps_tokens.append('(?P<%s>%s)' % (permalink_tokens[-1], self.wp_permalink_tokens[m.group(1)]))
            start = m.end()
        ps = ''.join(ps_tokens)
        #for m in self.wp_permalink_re.findall(ps):
        #    permalink_tokens.append(self.wp_permalink_map.get(m, m))
        #    ps = ps.replace('%' + m + '%', '(?P<%s>%s)' % (permalink_tokens[-1], self.wp_permalink_tokens[m]))
        if ps[-1] == '/':
            ps = ps[:-1]
        options['permalink_structure_orig'] = options['permalink_structure']
        options['permalink_structure'] = permalink_structure
        options['permalink_tokens'] = permalink_tokens
        options['permalink_ps'] = ps
        options['cookiehash'] = getattr(settings, 'WPF_COOKIEHASH', md5(self.site.siteurl).hexdigest())
        t = urlsplit(options['home'])
        if not t.path:
            t = SplitResult(t.scheme, t.netloc, '/', t.query, t.fragment)
        if t.netloc != self.domain:
            t = SplitResult(t.scheme, self.domain, t.path, t.query, t.fragment)
        options['home'] = urlunsplit(t)
        options['pingback_url'] = None
        if self.site.pingback_url:
            if self.site.subdomain_install:
                options['pingback_url'] = urlunsplit((t.scheme, self.domain, '/xmlrpc.php', '', ''))
            else:
                options['pingback_url'] = self.site.pingback_url
        t = urlsplit(options['siteurl'])
        if not t.path:
            t = SplitResult(t.scheme, t.netloc, '/', t.query, t.fragment)
        options['siteurl'] = urlunsplit(t)
        options['siteurl_mapped'] = urlunsplit((t.scheme, self.domain, t.path, t.query, t.fragment))
        # the path to the wordpress files is set in the siteurl site meta value
        path = self.site.siteurl_tokens.path
        if path == '/':
            path = ''
        options['admin_url'] = path + '/wp-admin/'
        options['includes_url'] = path + '/wp-includes/'
        options['themes_root_url'] = path + '/wp-content/themes/'
        options['theme_url'] = options['themes_root_url'] + '%s/' % options['template']
        options['media_url'] = path + ('/wp-content/blogs.dir/%s/' % self.blog_id)
        options['fileupload_path'] = urlsplit(options['fileupload_url']).path
        if self.site.global_favicon:
            options['favicon_path'] = path + '/wp-content/favicon.ico'
        else:
            options['favicon_path'] = path + '/wp-content/blogs.dir/%s/favicon.ico' % self.blog_id
        if self.site.global_robots:
            options['robots_path'] = path + '/wp-content/robots.txt'
        else:
            options['robots_path'] = path + '/wp-content/blogs.dir/%s/robots.txt' % self.blog_id
        if 'wp_user_roles' in options:
            capabilities = dict()
            for k, v in options['wp_user_roles'].items():
                for cap, active in v['capabilities'].items():
                    if active:
                        capabilities.setdefault(cap, list()).append(k)
            options['capabilities'] = capabilities
        elif blog_id != WP_DEFAULT_BLOG_ID:
            options['capabilities'] = type(self)._cache[WP_DEFAULT_BLOG_ID].capabilities
        else:
            raise ImproperlyConfigured("No capabilities found for default blog id '%s'." % blog_id)
        return options


# set the active blog to the default blog
if not WP_DEFAULT_BLOG_ID in Blog.site.blogs:
    raise ImproperlyConfigured("Default blog id '%s' set in settings.WP_DEFAULT_BLOG_ID not found in wp_blogs." % WP_DEFAULT_BLOG_ID)

blog = Blog.default_active()
