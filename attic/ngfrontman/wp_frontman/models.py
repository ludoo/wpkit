import os
import sys
import re
import datetime
import warnings

from urlparse import urlsplit, urlunsplit, SplitResult
from hashlib import md5
from threading import local
from types import ModuleType
from functools import partial
from copy import deepcopy
from warnings import warn

from django.conf import settings
from django.db import models, connection, connections, DatabaseError
from django.core.urlresolvers import set_urlconf
from django.db.utils import ConnectionDoesNotExist

from wp_frontman.lib.external.phpserialize import loads, phpobject


DB_PREFIX = getattr(settings, 'WPF_DB_PREFIX', 'wp_')
DB_CONNECTION = getattr(settings, 'WPF_DB_CONNECTION', 'default')
SITE_ID = getattr(settings, 'WPF_SITE_ID', 1)
#OPTIONS_PACKAGE = getattr(settings, 'WPF_OPTIONS_PACKAGE', 'wpf_blogs')


def strtobool(s):
    """Damn WP and its habit of using strings instead of ints for bools in MySQL"""
    try:
        i = int(s)
    except (TypeError, ValueError):
        return s
    return bool(i)


php_unserialize = partial(loads, object_hook=phpobject)


class Site(object):
    
    wp_frontman_template = dict(
        db_version                = None,
        wp_root                   = None,
        support_category_order    = False,
        use_sendfile              = False,
        builtin_post_types        = {
            'attachment': {
                '_builtin': True, 'capability_type': 'post', 'description': '',
                'exclude_from_search': False, 'has_archive': False, 'hierarchical': False,
                'label': 'Media', 'map_meta_cap': True, 'name': 'attachment',
                'public': True, 'publicly_queryable': True, 'rewrite': False,
                'taxonomies': {}
            },
            'page': {
                '_builtin': True, 'capability_type': 'page', 'description': '',
                'exclude_from_search': False, 'has_archive': False, 'hierarchical': True,
                'label': 'Pages', 'map_meta_cap': True, 'name': 'page',
                'public': True, 'publicly_queryable': False, 'rewrite': False,
                'taxonomies': {}
            },
            'post': {
                '_builtin': True, 'capability_type': 'post', 'description': '',
                'exclude_from_search': False, 'has_archive': False, 'hierarchical': False,
                'label': 'Posts', 'map_meta_cap': True, 'name': 'post',
                'public': True, 'publicly_queryable': True, 'rewrite': False,
                'taxonomies': {}
            }
        },
        builtin_taxonomies        = {
            'category': {
                '_builtin': True, 'hierarchical': True, 'label': 'Categories',
                'name': 'category', 'object_type': {0: 'post'},
                'public': True, 'query_var': 'category_name',
                'rewrite': {
                    'hierarchical': True, 'slug': 'category', 'with_front': True
                },
                'update_count_callback': '_update_post_term_count'
            },
            'post_format': {
                '_builtin': True, 'hierarchical': False, 'label': 'Format',
                'name': 'post_format', 'object_type': {0: 'post'},
                'public': True, 'query_var': 'post_format',
                'rewrite': {
                    'hierarchical': False, 'slug': 'type', 'with_front': True
                },
                'update_count_callback': ''
            },
            'post_tag': {
                '_builtin': True, 'hierarchical': False, 'label': 'Post Tags',
                'name': 'post_tag', 'object_type': {0: 'post'},
                'public': True, 'query_var': 'tag',
                'rewrite': {
                    'hierarchical': False, 'slug': 'tag', 'with_front': True
                },
                'update_count_callback': '_update_post_term_count'
            }
        },
        wp_auth_key               = None,
        wp_auth_salt              = None,
        wp_secret_key             = None,
        wp_secret_salt            = None,
        wp_secure_auth_key        = None,
        wp_secure_auth_salt       = None,
        wp_logged_in_key          = None,
        wp_logged_in_salt         = None,
        wp_nonce_key              = None,
        wp_nonce_salt             = None,
        rewrite_vars              = None,
        rewrite_feeds             = None,
    )
    
    meta_template = dict(
        dm_hash=None, admin_email=None, admin_user_id=int,
        registration=lambda v: False if v == 'none' else True,
        registrationnotification=lambda v: True if v == 'yes' else False,
        site_admins=php_unserialize, site_name=None, siteurl=None,
        subdomain_install=strtobool, wp_frontman=php_unserialize,
        auth_salt=str, cookiehash=None
    )
    
    site_id = None
    db_prefix = None
    using = None
    key = None
    mu = None
    models_modname = None
    _meta = None
    _blog_data = None
    _blog_path_map = None
    _blog_domain_map = None
    _blog_redirect_map = None
    
    def __init__(self, site_id=None, db_prefix=None, using=None, mu=None):
        self.site_id = site_id or SITE_ID
        self.db_prefix = db_prefix or DB_PREFIX
        self.using = using or DB_CONNECTION
        self.key = '%s-%s-%s' % (self.using, self.db_prefix, self.site_id)
        if mu is None:
            # try settings
            mu = getattr(settings, 'WPF_MULTIBLOG', None)
            if mu is None:
                # check the database for mu tables
                cursor = self.get_cursor()
                if cursor.execute("show tables like '%ssite'" % self.db_prefix):
                    mu = True
        self.mu = mu or False
        # sanity check
        if self.mu and not bool(self.get_cursor().execute("show tables like '%ssitemeta'" % self.db_prefix)):
            raise SystemError("Configured as multiblog ('WPF_MULTIBLOG' set to True in settings) but no site meta table found")
        self.models_modname = '%s.site_%s' % (__name__, self.key)

    def __repr__(self):
        return '<Site id %s using %s db prefix %s>' % (self.site_id, self.using, self.db_prefix)

    @property
    def models(self):
        if not self.models_modname in sys.modules:
            from wp_frontman import wp_models
            mod = ModuleType(self.models_modname)
            manager_db = None if self.using is None or self.using == 'default' else self.using
            # TODO: use a lock here so that each thread does not have to rebuild the module?
            models = []
            for c in wp_models.__site_models__:
                model = c._wp_model_factory(self, mod, manager_db)
                models.append(model.__name__)
            setattr(mod, '__models__', models)
            sys.modules[self.models_modname] = mod
        return sys.modules[self.models_modname]

    @property
    def meta(self):
        if self._meta is None:
            meta = dict()
            if self.mu:
                cursor = self.get_cursor()
                try:
                    cursor.execute("select meta_key, meta_value from %ssitemeta where site_id=%%s and left(meta_key, 1) != '_'" % self.db_prefix, (self.site_id,))
                except DatabaseError:
                    return dict()
                meta = dict()
                rows = dict(cursor.fetchall())
                for key, func in self.meta_template.items():
                    if key in rows:
                        try:
                            meta[key] = rows[key] if not callable(func) else func(rows[key])
                        except ValueError, e:
                            warn("Error in key %s for site %s: %s" % (key, self, e))
                            meta[key] = dict()
                    elif not callable(func):
                        meta[key] = func
            else:
                rows = Blog(1, self).options
                for key, func in self.meta_template.items():
                    if key in rows:
                        meta[key] = rows[key]
                    elif not callable(func):
                        meta[key] = func
                    else:
                        meta[key] = None
                meta['wp_frontman'] = rows.get('wp_frontman_site', dict())
            t = urlsplit(meta['siteurl'])
            meta['siteurl_tokens'] = t
            if len(t.path) > 1 and not t.path.endswith('/'):
                path = t.path + '/'
            elif not t.path:
                path = '/'
            else:
                path = t.path
            meta['pingback_url'] = urlunsplit((t.scheme, t.netloc, t.path + 'xmlrpc.php', '', ''))
            if not meta['cookiehash']:
                meta['cookiehash'] = md5(meta['siteurl'])
            wp_frontman = deepcopy(self.wp_frontman_template)
            wp_frontman.update(meta.get('wp_frontman', dict()))
            meta['wp_frontman'] = wp_frontman
            self._meta = meta
        return self._meta

    @property
    def blog_data(self):
        if self._blog_data is None:
            if not self.mu:
                self._blog_data = {1:dict(blog_id=1, domain=None, secondary_domain=None, path=None, archived=0, lang_id=0)}
            else:
                cursor = self.get_cursor()
                if cursor.execute("show tables like '%sdomain_mapping'" % self.db_prefix):
                    cursor.execute("""
                        select b.blog_id, if(dm.active=1, dm.domain, b.domain) as domain, if(dm.active=1, b.domain, NULL) as secondary_domain, b.path, b.archived, b.lang_id
                        from %sblogs b
                        left join %sdomain_mapping dm on dm.blog_id=b.blog_id
                        where site_id=%%s and deleted=0
                        """ % (self.db_prefix, self.db_prefix), (self.site_id,))
                else:
                    cursor.execute("""
                        select blog_id, domain, NULL as secondary_domain, path, archived, lang_id
                        from %sblogs
                        where site_id=%%s and deleted=0
                        """ % self.db_prefix, (self.site_id,))
                fields = [f[0] for f in cursor.description]
                self._blog_data = dict((r[0], dict(zip(fields, [v or None for v in r]))) for r in cursor.fetchall())
        return self._blog_data

    @property
    def blog_path_map(self):
        if self._blog_path_map is None:
            blogmap = dict()
            for id, data in self.blog_data.items():
                blogmap[(data['path'] or '').replace('/', '')] = id
            self._blog_path_map = blogmap
        return self._blog_path_map
    
    @property
    def blog_domain_map(self):
        if self._blog_domain_map is None:
            blogmap = dict()
            for id, data in self.blog_data.items():
                domain, secondary_domain = data['domain'], data['secondary_domain']
                if domain:
                    blogmap[domain] = id
                    if secondary_domain:
                        blogmap[secondary_domain] = domain
            self._blog_domain_map = blogmap
        return self._blog_domain_map
    
    def get_cursor(self):
        if self.using and self.using != 'default':
            try:
                _connection = connections[self.using]
            except ConnectionDoesNotExist, e:
                raise ValueError("No connection named '%s' in Site object: %s" % (self.using, e))
        else:
            _connection = connection
        return _connection.cursor()
    
    
    
class Blog(object):
    
    wp_frontman_template = dict(
        db_version            = 1,
        cache                 = dict(enabled=False),
        preformatter          = dict(enabled=False),
        feedburner            = dict(enabled=False),
        images                = dict(enabled=False),
        analytics             = dict(enabled=False),
        custom_taxonomies     = dict(),
        custom_post_types     = dict(),
    )
    
    options_template = dict(
        admin_email=None, avatar_default=None, avatar_rating=None, blacklist_keys=None,
        blog_charset=str, blog_public=strtobool, blogdescription=None, blogname=None, category_base=None,
        category_children=php_unserialize, comment_max_links=int, comment_moderation=bool,
        comment_order=None, comment_registration=strtobool, comment_whitelist=strtobool,
        comments_notify=strtobool, comments_per_page=int, current_theme=None, date_format=None,
        default_category=int, default_comment_status=None,
        default_comments_page=dict(newest='last', oldest='first').get,
        default_link_category=int, default_ping_status=None, default_pingback_flag=strtobool,
        fileupload_url=None, home=None, html_type=None, language=None, links_recently_updated_time=int,
        links_updated_date_format=None, mailserver_login=None, mailserver_pass=None,
        mailserver_port=int, mailserver_url=None, moderation_notify=strtobool,
        page_comments=strtobool, permalink_structure=None, ping_sites=None, post_count=None,
        posts_per_page=int, posts_per_rss=int, require_name_email=strtobool,
        rewrite_rules=php_unserialize, rss_language=None, rss_use_excerpt=bool,
        show_avatars=strtobool, siteurl=None, start_of_week=int, tag_base=None, template=None,
        thread_comments=strtobool, thread_comments_depth=int, time_format=None, timezone_string=None,
        upload_path=None, upload_url_path=None, use_trackback=strtobool, WPLANG=None, wp_user_roles=php_unserialize,
        wordpress_api_key=None, defensio_key=None, wp_frontman=php_unserialize, wp_frontman_site=php_unserialize,
    )
    
    wp_permalink_tokens = dict(
        year='[0-9]{4}', monthnum='[0-9]{1,2}', day='[0-9]{1,2}', hour='[0-9]{1,2}',
        minute='[0-9]{1,2}', second='[0-9]{1,2}', postname='[^/]+', post_id='[0-9]+',
        category='.+?', tag='.+?', author='[^/]+', pagename='[^/]+?', search='.+'
    )
    
    wp_permalink_map = dict(
        monthnum='month', postname='slug', post_id='id', search='q'
    )

    wp_permalink_re = re.compile(r'%([a-z_]+)%')
    
    _blogs = dict()
    _local = local()
    
    site = Site()
    
    blog_id = None
    db_prefix = None
    blog_key = None
    models_modname = None
    urlconf = 'urls'
    _options = None
    _post_types = None
    _taxonomies = None
    _cache = None
    
    @classmethod
    def factory(cls, blog_id, site=None, active=True):
        site = site or cls.site
        obj = cls(blog_id, site)
        if active and site is cls.site:
            set_urlconf(obj.urlconf)
            cls._local.active_blog = obj
        return obj
    
    @classmethod
    def get_active(cls):
        return getattr(cls._local, 'active_blog', None)
    
    @classmethod
    def get_blogs(cls, site=None):
        site = site or cls.site
        for blog_id in site.blog_data:
            yield(cls(blog_id))
    
    def __new__(cls, *args, **kw):
        if args:
            blog_id = args[0]
        elif 'blog_id' in kw:
            blog_id = kw['blog_id']
        else:
            raise TypeError("No blog_id, cannot create Blog instance")
        if len(args) == 2:
            site = args[-1]
        elif 'site' in kw:
            site = kw['site']
        else:
            site = cls.site
        site = site or cls.site
        if blog_id not in site.blog_data:
            raise ValueError("No blog with id '%s' in site '%s'" % (blog_id, site.site_id))
        key = (site.key, blog_id)
        if key in cls._blogs:
            return cls._blogs[key]
        obj = super(Blog, cls).__new__(cls)
        cls._blogs[key] = obj
        return obj
    
    def __init__(self, blog_id, site=None):
        if 'blog_id' in self.__dict__:
            return
        self.blog_id = blog_id
        if site is not None:
            self.site = site
        self.domain = self.secondary_domain = self.path = self.archived = self.lang_id = None
        for k, v in self.site.blog_data[blog_id].items():
            setattr(self, k, v)
        if self.path:
            self.path = self.path if self.path[0] == '/' else '/' + self.path
            self.path = self.path if self.path[-1] == '/' else self.path + '/'
        self.db_prefix = DB_PREFIX if self.blog_id == 1 else '%s%s_' % (DB_PREFIX, self.blog_id)
        self.blog_key = "%s_%s" % (self.site.key, self.blog_id)
        self.models_modname = 'wp_frontman.models_blog_%s_%s' % (self.site.key, self.blog_id)
        self.urlrules_modname = 'wp_frontman.blog_urls.urls_%s_%s' % (self.site.key, self.blog_id)
        self._options = None
        self._post_types = None
        self._taxonomies = None
        self._cache = dict()
        
    @property
    def cache(self):
        return self._cache

    @property
    def post_types(self):
        if self._post_types is None:
            post_types = self.site.meta['wp_frontman']['builtin_post_types'].items()
            if self.options['wp_frontman']['custom_post_types'] and isinstance(self.options['wp_frontman']['custom_post_types'], dict):
                post_types += self.options['wp_frontman']['custom_post_types'].items()
            self._post_types = dict(post_types)
        return self._post_types
    
    @property
    def taxonomies(self):
        if self._taxonomies is None:
            taxonomies = self.site.meta['wp_frontman']['builtin_taxonomies'].items()
            if self.options['wp_frontman']['custom_taxonomies'] and isinstance(self.options['wp_frontman']['custom_taxonomies'], dict):
                taxonomies += self.options['wp_frontman']['custom_taxonomies'].items()
            self._taxonomies = dict(taxonomies)
        return self._taxonomies
        
    @property
    def options(self):
        if self._options is None:
            options = dict()
            db_prefix = DB_PREFIX if self.blog_id == 1 else "%s%s_" % (DB_PREFIX, self.blog_id)
            cursor = self.site.get_cursor()
            if not cursor.execute("select option_name, option_value from %soptions where autoload='yes' order by option_name" % db_prefix):
                raise SystemError("No options for blog %s" % self)
            rows = dict(cursor.fetchall())
            for key, func in self.options_template.items():
                if key in rows:
                    try:
                        options[key] = rows[key] if not callable(func) else func(rows[key])
                    except ValueError, e:
                        warn("Error in key %s for blog %s: %s" % (key, self, e))
                        options[key] = dict()
                    del rows[key]
                elif not callable(func):
                    options[key] = func
            for k, v in rows.items():
                if k in options:
                    continue
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    try:
                        v = php_unserialize(v)
                    except ValueError:
                        pass
                options[k] = v

            permalink_structure = options['permalink_structure']
            if not permalink_structure:
                raise SystemError("No 'permalink_structure' option found in options for blog '%s'" % self)
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
                ps_tokens.append(ps[start:m.start()]) #re.escape(ps[start:m.start()]))
                permalink_tokens.append(self.wp_permalink_map.get(m.group(1), m.group(1)))
                ps_tokens.append('(?P<%s>%s)' % (permalink_tokens[-1], self.wp_permalink_tokens[m.group(1)]))
                start = m.end()
            ps_tokens.append(ps[start:])
            ps = ''.join(ps_tokens)
            #for m in self.wp_permalink_re.findall(ps):
            #    permalink_tokens.append(self.wp_permalink_map.get(m, m))
            #    ps = ps.replace('%' + m + '%', '(?P<%s>%s)' % (permalink_tokens[-1], self.wp_permalink_tokens[m]))
            if ps and ps[-1] == '/':
                ps = ps[:-1]
            options['permalink_structure_orig'] = options['permalink_structure']
            options['permalink_structure'] = permalink_structure
            options['permalink_tokens'] = permalink_tokens
            options['permalink_ps'] = ps
            home_tokens = urlsplit(options['home'])
            if not home_tokens.path:
                home_tokens = SplitResult(home_tokens.scheme, home_tokens.netloc, '/', home_tokens.query, home_tokens.fragment)
            siteurl_tokens = urlsplit(options['siteurl'])
            if not siteurl_tokens.path:
                siteurl_tokens = SplitResult(siteurl_tokens.scheme, siteurl_tokens.netloc, '/', siteurl_tokens.query, siteurl_tokens.fragment)
            if self.site.mu:
                if home_tokens.netloc != self.domain:
                    home_tokens = SplitResult(home_tokens.scheme, self.domain, home_tokens.path, home_tokens.query, home_tokens.fragment)
                options['siteurl_mapped'] = urlunsplit((siteurl_tokens.scheme, self.domain, siteurl_tokens.path, siteurl_tokens.query, siteurl_tokens.fragment))
                if self.site.meta['pingback_url']:
                    if self.site.meta['subdomain_install']:
                        options['pingback_url'] = urlunsplit((t.scheme, self.domain, '/xmlrpc.php', '', ''))
                    else:
                        pingback_tokens = urlsplit(self.site.meta['pingback_url'])
                        options['pingback_url'] = urlunsplit((pingback_tokens.scheme, pingback_tokens.netloc, self.path + 'xmlrpc.php', '', ''))
                path = self.site.meta['siteurl_tokens'].path
            else:
                if not options.get('pingback_url'):
                    if len(siteurl_tokens.path) > 1 and not siteurl_tokens.path.endswith('/'):
                        path = siteurl_tokens.path + '/'
                    elif not siteurl_tokens.path:
                        path = '/'
                    else:
                        path = siteurl_tokens.path
                    options['pingback_url'] = urlunsplit((siteurl_tokens.scheme, siteurl_tokens.netloc, siteurl_tokens.path + 'xmlrpc.php', '', ''))
                options['siteurl_mapped'] = urlunsplit((siteurl_tokens.scheme, siteurl_tokens.netloc, siteurl_tokens.path, siteurl_tokens.query, siteurl_tokens.fragment))
                path = siteurl_tokens.path
            options['home'] = urlunsplit(home_tokens)
            options['siteurl'] = urlunsplit(siteurl_tokens)
            # the path to the wordpress files is set in the siteurl site meta value
            if path == '/':
                path = ''
            options['admin_url'] = path + '/wp-admin/'
            options['includes_url'] = path + '/wp-includes/'
            options['themes_root_url'] = path + '/wp-content/themes/'
            options['theme_url'] = options['themes_root_url'] + '%s/' % options['template']
            options['media_url'] = path + ('/wp-content/blogs.dir/%s/' % self.blog_id)
            options['upload_path'] = options['upload_path'] or 'wp-content/uploads'
            if self.site.mu:
                wp_root = self.site.meta.get('wp_frontman', dict()).get('wp_root')
            else:
                wp_root = options.get('wp_frontman_site', dict()).get('wp_root')
            upload_path = options['upload_path'].replace('/', os.path.sep)
            wp_root = wp_root.replace('/', os.path.sep)
            if upload_path[0] != os.path.sep and wp_root and wp_root[0] == os.path.sep:
                options['upload_abspath'] = wp_root + ('' if wp_root[-1] == os.path.sep else os.path.sep) + upload_path
            else:
                options['upload_abspath'] = os.path.abspath(upload_path)
            if options.get('fileupload_url'):
                options['fileupload_path'] = urlsplit(options['fileupload_url']).path
            else:
                options['fileupload_path'] = path + '/wp-content/uploads/'
            if 'wp_user_roles' in options:
                capabilities = dict()
                for k, v in options['wp_user_roles'].items():
                    for cap, active in v['capabilities'].items():
                        if active:
                            capabilities.setdefault(cap, list()).append(k)
                options['capabilities'] = capabilities
            elif self.blog_id != 1:
                options['capabilities'] = Blog(1, self.site).options['capabilities']
            else:
                raise SystemError("No capabilities found for default blog id 1.")
            wp_frontman = deepcopy(self.wp_frontman_template)
            wp_frontman.update(options.get('wp_frontman', dict()))
            options['wp_frontman'] = wp_frontman
            self._options = options
        return self._options
        
    @property
    def models(self):
        if not self.models_modname in sys.modules:
            from wp_frontman import wp_models
            mod = ModuleType(self.models_modname)
            manager_db = None if self.site.using is None or self.site.using == 'default' else self.site.using
            # TODO: use a lock here so that each thread does not have to rebuild the module?
            for m in self.site.models.__models__:
                setattr(mod, m, getattr(self.site.models, m))
            for c in wp_models.__blog_models__:
                c._wp_model_factory(self, mod, manager_db)
            sys.modules[self.models_modname] = mod
        return sys.modules[self.models_modname]
    
    @property
    def urlconf(self):
        if not self.urlrules_modname in sys.modules:
            try:
                __import__(self.urlrules_modname)
            except ImportError:
                # check if we have to append or prepend the project-wide urlconf
                if self.options['wp_frontman']['urlconf'] in ('append', 'prepend'):
                    root_urlpatterns = None
                    if not settings.ROOT_URLCONF in sys.modules:
                        try:
                            root_urls = __import__(settings.ROOT_URLCONF)
                        except ImportError, e:
                            warnings.warn("Cannot import root urlconf %s" % settings.ROOT_URLCONF)
                        else:
                            root_urlpatterns = sys.modules[settings.ROOT_URLCONF].urlpatterns
                from django.conf.urls.defaults import patterns
                mod = ModuleType(self.urlrules_modname)
                urlpatterns = patterns('', *self.urlpatterns())
                if self.options['wp_frontman']['urlconf'] == 'prepend' and root_urlpatterns:
                    urlpatterns = root_urlpatterns + urlpatterns
                elif self.options['wp_frontman']['urlconf'] == 'append' and root_urlpatterns:
                    urlpatterns += root_urlpatterns
                mod.urlpatterns = urlpatterns
                sys.modules[self.urlrules_modname] = mod
        return self.urlrules_modname
    
    def urlpatterns(self):
        path = urlsplit(self.options['home']).path
        if not path.endswith('/'):
            path += '/'
        if path == '/':
            path = ''
        if path and path.startswith('/'):
            path = path[1:]
        rewrite_vars = dict((i[0], i[1]) for i in self.site.meta['wp_frontman']['rewrite_vars'].values())
        #if 'rewrite' in self.options['wp_frontman']:
        rewrite_prefixes = dict(self.options['wp_frontman']['rewrite'])
        #else:
        #    rewrite_prefixes = dict(self.site.meta['wp_frontman']['rewrite'])
        pattern_list = []
        page_fragment = rewrite_prefixes['pagination_base'] + '/(?P<page>[0-9]+)/'
        comment_page_fragment = 'comment-page-(?P<page>[0-9]+)/'
        # home
        pattern_list.append((r'^%s$' % path, 'wp_frontman.views.index', dict(), 'wpf_index'))
        pattern_list.append((r'^%s%s$' % (path, page_fragment), 'wp_frontman.views.index', dict(), 'wpf_index'))
        # favicon and robots
        pattern_list.append((r'^favicon.ico$', 'wp_frontman.views.favicon', dict(), 'wpf_favicon'))
        pattern_list.append((r'^robots.txt$', 'wp_frontman.views.robots', dict(), 'wpf_robots'))
        # feed
        pattern_list.append((r'^%sfeed/$' % path, 'wp_frontman.views.feed', dict(), 'wpf_feed'))
        pattern_list.append((r'^%scomments/feed/$' % path, 'wp_frontman.views.feed_comments', dict(), 'wpf_feed_comments'))
        feeds = (
            'wp-atom.php|wp-rdf.php|wp-rss.php|wp-rss2.php|wp-feed.php|wp-commentsrss2.php',
            'feed|rdf|rss|rss2|atom',
        )
        for f in feeds:
            pattern_list.append((r'^%s(?:feed/)?(?:%s)%s$' % (path, f, '' if '.php' in f else '/'), 'wp_frontman.views.feed'))
        # files
        if self.site.mu:
            pattern_list.append((r'^%sfiles/(?P<filepath>.*?)$' % path, 'wp_frontman.views.media', dict(), 'wpf_media'))
        taxonomy_single = r'^%s%%s/(?P<slug>[^/]+)' % path
        taxonomy_hierarchical = r'^%s%%s/(?P<hierarchy>(?:[^/]+/)+)(?P<slug>[^/]+)' % path
        # category
        base = rewrite_prefixes['category_base'] or 'category'
        pattern_list.append(((taxonomy_single % base) + '/' + page_fragment + '$', 'wp_frontman.views.taxonomy', dict(taxonomy='category'), 'wpf_category'))
        pattern_list.append(((taxonomy_single % base) + '/$', 'wp_frontman.views.taxonomy', dict(taxonomy='category'), 'wpf_category'))
        pattern_list.append(((taxonomy_hierarchical % base) + '/' + page_fragment + '$', 'wp_frontman.views.taxonomy', dict(taxonomy='category'), 'wpf_category'))
        pattern_list.append(((taxonomy_hierarchical % base) + '/$', 'wp_frontman.views.taxonomy', dict(taxonomy='category'), 'wpf_category'))
        # tag
        base = rewrite_prefixes['tag_base'] or 'tag'
        pattern_list.append(((taxonomy_single % base) + '/$', 'wp_frontman.views.taxonomy', dict(taxonomy='tag'), 'wpf_tag'))
        pattern_list.append(((taxonomy_single % base) + '/' + page_fragment + '$', 'wp_frontman.views.taxonomy', dict(taxonomy='tag'), 'wpf_tag'))
        # custom taxonomies
        for k, v in self.options['wp_frontman']['custom_taxonomies'].items():
            pattern_list.append(((taxonomy_single % v['rewrite_slug']) + '/$', 'wp_frontman.views.taxonomy', dict(taxonomy=k), 'wpf_' + k))
            pattern_list.append(((taxonomy_single % v['rewrite_slug']) + '/' + page_fragment + '$', 'wp_frontman.views.taxonomy', dict(taxonomy=k), 'wpf_' + k))
            if v['rewrite_hierarchical']:
                pattern_list.append(((taxonomy_hierarchical % v['rewrite_slug']) + '/$', 'wp_frontman.views.taxonomy', dict(taxonomy=k), 'wpf_' + k))
                pattern_list.append(((taxonomy_hierarchical % v['rewrite_slug']) + '/' + page_fragment + '$', 'wp_frontman.views.taxonomy', dict(taxonomy=k), 'wpf_' + k))
        # archives
        pattern_list.append((r'^%s(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/$' % path, 'wp_frontman.views.archives', dict(), 'wpf_archive'))
        pattern_list.append((r'^%s(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/%s$' % (path, page_fragment), 'wp_frontman.views.archives', dict(), 'wpf_archive'))
        pattern_list.append((r'^%s(?P<year>[0-9]{4})/$' % path, 'wp_frontman.views.archives', dict(), 'wpf_archive'))
        pattern_list.append((r'^%s(?P<year>[0-9]{4})/%s$' % (path, page_fragment), 'wp_frontman.views.archives', dict(), 'wpf_archive'))
        # author
        pattern_list.append(('^%s%s/(?P<slug>[^/]+)/$' % (path, rewrite_prefixes['author_base']), 'wp_frontman.views.author', dict(), 'wpf_author'))
        pattern_list.append(('^%s%s/(?P<slug>[^/]+)/%s$' % (path, rewrite_prefixes['author_base'], page_fragment), 'wp_frontman.views.author', dict(), 'wpf_author'))
        # search
        pattern_list.append(('^%s%s/$' % (path, rewrite_prefixes['search_base']), 'wp_frontman.views.search', dict(), 'wpf_search'))
        pattern_list.append(('^%s%s/(?P<q>.+)/$' % (path, rewrite_prefixes['search_base']), 'wp_frontman.views.search', dict(), 'wpf_search'))
        pattern_list.append(('^%s%s/(?P<q>.+)/%s$' % (path, rewrite_prefixes['search_base'], page_fragment), 'wp_frontman.views.search', dict(), 'wpf_search'))
        # post formats
        pattern_list.append((r'^%stype/(?P<post_format>[^/]+)/$' % path, 'wp_frontman.views.taxonomy', dict(taxonomy='post_format'), 'wpf_post_format'))
        pattern_list.append((r'^%stype/(?P<post_format>[^/]+)/%s$' % (path, page_fragment), 'wp_frontman.views.taxonomy', dict(taxonomy='post_format'), 'wpf_post_format'))
        # posts
        ps = self.options['permalink_ps']
        pattern_list.append(('^%s%s/$' % (path, ps), 'wp_frontman.views.post', dict(), 'wpf_post'))
        pattern_list.append(('^%s%s/%s$' % (path, ps, comment_page_fragment), 'wp_frontman.views.post', dict(), 'wpf_post'))
        # attachments
        pattern_list.append(('^%s%s/attachment/(?P<attachment_slug>[^/]+)/$' % (path, ps), 'wp_frontman.views.post', dict(), 'wpf_attachment'))
        pattern_list.append(('^%s%s/attachment/(?P<attachment_slug>[^/]+)/%s$' % (path, ps, comment_page_fragment), 'wp_frontman.views.post', dict(), 'wpf_attachment'))
        return pattern_list
    
    @classmethod
    def find_blog_id(cls, domain=None, path=None):
        if not cls.site.mu:
            return 1
        if not cls.site.meta['subdomain_install']:
            if path is None:
                return
            try:
                path = [p for p in path.split('/') if p][0]
            except IndexError:
                path = ''
            #file('/tmp/wpf.log', 'a+').write("--- blog_path_map %s\n" % cls.site.blog_path_map)
            blog_id = cls.site.blog_path_map.get(path) or 1
            #file('/tmp/wpf.log', 'a+').write("--- path %s blog_id %s\n" % (path, blog_id))
        elif domain is None:
            return
        else:
            blog_id = cls.site.blog_domain_map.get(domain)
        if not blog_id:
            return
        if isinstance(blog_id, basestring):
            raise ValueError(basestring)
        return blog_id

    def __repr__(self):
        return '<Blog id %s site id %s %s db prefix %s>' % (self.blog_id, self.site.site_id, self.site.using, self.site.db_prefix)
    

class Job(models.Model):
    
    blog_id = models.IntegerField(db_index=True)
    process = models.CharField(max_length=48)
    tstamp = models.DateTimeField(blank=True, default=datetime.datetime.now)
    error = models.BooleanField(blank=True, default=False)
    object_id = models.IntegerField(blank=True, null=True)
    message = models.CharField(blank=True, null=True, max_length=255)
    
    class Meta:
        db_table = '%swpf_job' % DB_PREFIX
        unique_together = ('blog_id', 'process')
        
