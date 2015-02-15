import os
import sys
import datetime
import logging

from types import ModuleType
from functools import partial
from urlparse import urljoin, urlsplit, urlunsplit, SplitResult

from django.apps import apps, AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.conf.urls import patterns
from django.core.urlresolvers import reverse, NoReverseMatch
from django.utils.lru_cache import lru_cache
from django.utils.functional import cached_property
from django.db import models, connections, router

from . import managers
from .wp.options import WPSiteOptions, WPBlogOptions, WPPostMeta
from .wp import permalinks
from .wp.utils import php_unserialize, strip_html
from .wp.content import POST_MORE_RE


app = apps.get_app_config('wpkit')
logger = logging.getLogger('wpkit.models')

DB_PREFIX = app.wp_config.get('table_prefix')
SUBDOMAIN_INSTALL = app.wp_config.get('SUBDOMAIN_INSTALL', False)
SUPPORTS_DOMAIN_MAPPING = None # set later on
LRU_MAXSIZE = getattr(settings, 'WPKIT_LRU_MAXSIZE', None)
POST_TYPES = {
    'post': {},
    'page': {'hierarchical': True},
    'attachment': {},
    'revision': {},
    'navigation_menu': {}
}
TAXONOMIES = {
    'category': {
        'hierarchical': True, 'plural':'categories', 'object': 'post'
    },
    'post_tag':  {
        'object': 'post', 'name': 'tag',
    },
    'post_format':  {
        'object': 'post', 'name':'format',
        'normalize_slug': lambda s: s if not s or not s.startswith('post-format-') else s[12:],
        'normalize_name': lambda s: s if not s or not s.lower().startswith('post-format-') else s[12:],
    },
    'nav_menu': {
        'object': 'nav_menu_item'
    },
    'link_category' : {
        'plural':'link_categories', 'object': 'link'
    }
}


def named_partial(func, *args, **kw):
    new_func = partial(func, *args, **kw)
    new_func.__name__ = func.__name__
    new_func.__doc__ = func.__doc__
    new_func.__module__ = func.__module__
    return new_func


class RuntimeAppConfig(AppConfig):
    
    path = os.path.dirname(__file__)
    
    def __init__(self, app_name, app_module, label):
        self.label = label
        super(RuntimeAppConfig, self).__init__(app_name, app_module)


class User(models.Model):
    id = models.BigIntegerField(primary_key=True, db_column='ID')
    login = models.CharField(max_length=180, db_column='user_login')
    passwd = models.CharField(max_length=192, db_column='user_pass')
    nicename = models.CharField(max_length=150, db_column='user_nicename')
    email = models.CharField(max_length=300, db_column='user_email')
    url = models.CharField(max_length=300, db_column='user_url')
    registered = models.DateTimeField(blank=True, default=datetime.datetime.now, db_column='user_registered')
    activation_key = models.CharField(max_length=180, db_column='user_activation_key')
    status = models.IntegerField(db_column='user_status')
    display_name = models.CharField(max_length=750)
    spam = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)
    
    class Meta:
        db_table = DB_PREFIX + 'users'
        managed = False

    def __repr__(self):
        return '<User object id %s wp prefix %s>' % (self.id, DB_PREFIX)
    
    def __cmp__(self, other):
        return isinstance(other, User) and cmp(self.id, other.id)
    
    def __hash__(self):
        return self.id
        
    @property
    @lru_cache(maxsize=LRU_MAXSIZE)
    def meta(self):
        if not hasattr(self, '_usermeta'):
            self._usermeta = dict(
                (m.name, m.value) for m in self.usermeta_set.select_related('user').all()
            )
        return self._usermeta

    def __unicode__(self):
        return u"%s id %s status %s" % (self.login, self.id, self.status)
    
    def get_absolute_url(self):
        return reverse('wpkit_author', kwargs={'slug':self.login})
    
    @cached_property
    def url(self):
        return self.get_absolute_url()


class UserMeta(models.Model):
    user = models.ForeignKey('User')
    id = models.BigIntegerField(primary_key=True, db_column='umeta_id')
    key = models.CharField(max_length=765, blank=True, db_column='meta_key')
    value = models.TextField(blank=True, db_column='meta_value')
    
    class Meta:
        db_table = DB_PREFIX + 'usermeta'
        managed = False

    @property
    def parsed_value(self):
        if hasattr(self, '_parsed_value'):
            return self._parsed_value
        self._parsed_value = v = self.value
        if v and isinstance(v, basestring) and len(v) >= 3 and v[1] == ':':
            try:
                self._parsed_value = php_unserialize(v)
            except ValueError:
                pass
        return self._parsed_value


### use the User model to check for the domain mapping plugin
with connections[router.db_for_read(User)].cursor() as cursor:
    SUPPORTS_DOMAIN_MAPPING = cursor.execute(
        "show tables like '%sdomain_mapping'" % DB_PREFIX
    ) > 0
    

class Site(models.Model):
    
    domain = models.CharField(max_length=200)
    path = models.CharField(max_length=100)
    
    objects = managers.SiteManager()
    
    class Meta:
        db_table = DB_PREFIX + 'site'
        unique_together = (('domain', 'path'),)
        managed = False

    def __repr__(self):
        return '<Site object id %s wp prefix %s>' % (self.id, DB_PREFIX)
    
    def __cmp__(self, other):
        return isinstance(other, Site) and cmp(self.id, other.id)
    
    def __hash__(self):
        return self.id
    
    @property
    def blogs(self):
        # typically used only once from our middleware, no need to cache
        qs = self.blog_set.all()
        if SUPPORTS_DOMAIN_MAPPING:
            qs = qs.prefetch_related('domainmapping_set')
        return list(qs)
    
    @property
    @lru_cache(maxsize=LRU_MAXSIZE)
    def meta(self):
        # TODO: check meta.subdomain_install against self.subdomain_install?
        return WPSiteOptions(self.sitemeta_set.values_list())
    
    @lru_cache(maxsize=LRU_MAXSIZE)
    def get_blog(self, id):
        # use a method so we can cache results
        return self.blog_set.get(id=id)
    

class SiteMeta(models.Model):
    id = models.BigIntegerField(primary_key=True, db_column='meta_id')
    site = models.ForeignKey(Site)
    key = models.CharField(max_length=255, db_column='meta_key')
    value = models.TextField(db_column='meta_value')
    
    class Meta:
        db_table = DB_PREFIX + 'sitemeta'
        managed = False
        
        
class Blog(models.Model):
    id = models.BigIntegerField(primary_key=True, db_column='blog_id')
    site = models.ForeignKey(Site)
    domain = models.CharField(max_length=200)
    path = models.CharField(max_length=100)
    registered = models.DateTimeField()
    last_updated = models.DateTimeField()
    public = models.BooleanField(default=True)
    archived = models.BooleanField(default=False)
    mature = models.BooleanField(default=False)
    spam = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)
    lang_id = models.IntegerField()
    
    class Meta:
        db_table = DB_PREFIX + 'blogs'
        unique_together = (('domain', 'path'),)
        managed = False
        
    def __repr__(self):
        return '<Blog object id %s site id %s wp prefix %s>' % (self.id, self.site_id, DB_PREFIX)
    
    def __cmp__(self, other):
        return isinstance(other, Blog) and cmp(
            (self.site_id, self.id), (other.site_id, other.id)
        )
    
    def __hash__(self):
        return hash((self.site_id, self.id))

    def __init__(self, *args, **kw):
        super(Blog, self).__init__(*args, **kw)
        self.db_prefix = DB_PREFIX
        if self.id != 1:
            self.db_prefix += ('%s_' % self.id)

    @property
    @lru_cache(maxsize=LRU_MAXSIZE)
    def options(self):
        return WPBlogOptions(
            self.models.BlogOption.objects.filter(autoload='yes').values_list()
        )
    
    @property
    @lru_cache(maxsize=LRU_MAXSIZE)
    def primary_domain(self):
        if hasattr(self, 'domainmapping_set'):
            try:
                return self.domainmapping_set.filter(active=True)[0].domain
            except IndexError:
                pass
        return self.domain
    
    @cached_property
    def post_types(self):
        post_types = dict((k, v.copy()) for k, v in POST_TYPES.items())
        custom_types = self.settings.get('post_types')
        if custom_types and isinstance(custom_types, dict):
            post_types.update(custom_types)
        return post_types
    
    @cached_property
    def taxonomies(self):
        taxonomies = dict((k, v.copy()) for k, v in TAXONOMIES.items())
        custom_taxonomies = self.settings.get('taxonomies')
        if custom_taxonomies and isinstance(custom_taxonomies, dict):
            taxonomies.update(custom_taxonomies)
        return taxonomies
    
    @cached_property
    def bases(self):
        bases = {
            'category': self.options.category_base.replace('/', ''),
            'tag': self.options.tag_base.replace('/', ''),
        }
        custom_bases = self.settings.get('bases')
        if custom_bases and isinstance(custom_bases, dict):
            bases.update(custom_bases)
        return bases

    @cached_property
    def home(self):
        tokens = urlsplit(self.options.home)
        if tokens.netloc != self.primary_domain:
            return urlunsplit(SplitResult(
                tokens.scheme, self.primary_domain, tokens.path, tokens.query, tokens.fragment
            ))
        return self.options.home
    
    @cached_property
    def pingback_url(self):
        if self.site.meta.pingback_url:
            tokens = urlsplit(self.site.meta.pingback_url)
            if SUBDOMAIN_INSTALL:
                return urlunsplit(SplitResult(
                    tokens.scheme, self.primary_domain, tokens.path, tokens.query, tokens.fragment
                ))
            else:
                return urlunsplit(SplitResult(
                    tokens.scheme, tokens.netloc, self.path+'xmlrpc.php', '', ''
                ))

    @property
    def upload_path(self):
        if self.options.upload_path:
            return self.options.upload_path
        return os.path.join(
            app.wp_root,
            'wp-content/blogs.dir/%s/files' % self.id
        )
        
    @property
    def upload_url_path(self):
        if self.options.upload_url_path:
            return self.options.upload_url_path
        path = self.upload_path
        if not path.startswith(app.wp_root):
            return
        return path[len(app.wp_root):]
                
    _base_settings = {
        'date_format':getattr(settings, 'DATE_FORMAT', None)
    }
        
    @cached_property
    def settings(self):
        blogs_settings = getattr(settings, 'WPKIT_BLOGS', {})
        if not isinstance(blogs_settings, dict):
            raise ImproperlyConfigured("If settings.WPKIT_BLOGS is set, it must be a dictionary")
        blog_settings = blogs_settings.get((self.site_id, self.id), {})
        if not isinstance(blog_settings, dict):
            raise ImproperlyConfigured("Settings for blog %s must be a dictionary" % self.id)
        base_settings = self._base_settings.copy()
        base_settings.update(blog_settings)
        return base_settings
    
    def settings_reset(self, new_settings=None):
        # used for tests
        if 'settings' in self.__dict__:
            del self.__dict__['settings']
        if isinstance(new_settings, dict):
            base_settings = self._base_settings.copy()
            base_settings.update(new_settings)
            self.__dict__['settings'] = base_settings
    
    @property
    def modname(self):
        return 'wpkit.site_%s_blog_%s' % (self.site_id, self.id)
    
    @property
    def module(self):
        name = self.modname
        if name not in sys.modules:
            sys.modules[name] = ModuleType(name)
        return sys.modules[name]
    
    @cached_property
    def ps_tokens(self):
        return permalinks.process_permalink(
            self.options.permalink_structure
        )[0]
    
    @property
    def urlconf(self):
        
        modname = self.modname + '.urls'
        
        if modname in sys.modules:
            return sys.modules[modname]
        
        # TODO: prepend/append user-defined URLs from settings
        
        # store the permalink_structure tokens so that we can reuse them later
        # to determine what keyword args to pass to the post url pattern
        self._ps_tokens, ps_pattern = permalinks.process_permalink(self.options.permalink_structure)
        
        urlpatterns = permalinks.wp_urlpatterns(
            urlsplit(self.home).path, ps_pattern, self.bases
        )
        
        module = ModuleType(modname)
        module.urlpatterns = patterns('', *urlpatterns)
        self.module.urls = sys.modules[modname] = module
        
        return module
        
    @property
    def models(self):
        modname = self.modname + '.models'
        app_label = 'wpkit_site_%s_blog_%s' % (self.site_id, self.id)
        
        if modname in sys.modules:
            return sys.modules[modname]
        
        # TODO: maybe also inject user-defined functions here,
        #       to allow checking for different plugins
        
        # check if this blog has the my category order plugin installed
        with connections[router.db_for_read(User)].cursor() as cursor:
            SUPPORTS_TERM_ORDERING = cursor.execute(
                "show columns in %sterms like 'term_order'" % self.db_prefix
            ) > 0
        
        module = ModuleType(modname)
        
        # options
        module.BlogOption = type('BlogOption', (BlogOption,), {
            '__module__': module.__name__,
            'Meta':type('Meta', (BlogOption.Meta, object), {
                '__module__': module.__name__,
                'app_label': app_label,
                'db_table': self.db_prefix+BlogOption._meta.db_table
            }),
            '_wp_blog': self
        })
        
        # taxonomy term
        module.TaxonomyTerm = type('TaxonomyTerm', (TaxonomyTerm,), {
            '__module__': module.__name__,
            'Meta':type('Meta', (TaxonomyTerm.Meta, object),  {
                '__module__': module.__name__,
                'app_label': app_label,
                'db_table': self.db_prefix+TaxonomyTerm._meta.db_table,
                'ordering': ('name',) if not SUPPORTS_TERM_ORDERING else ('order', 'name')
            }),
            '_wp_blog': self,
            'order': None if not SUPPORTS_TERM_ORDERING else models.IntegerField(
                db_column='term_order', db_index=True
            )
        })
        
        # term relationship
        module.PostTermRelationship = type('PostTermRelationship', (PostTermRelationship,), {
            '__module__': module.__name__,
            'Meta':type('Meta', (PostTermRelationship.Meta, object),  {
                '__module__': module.__name__,
                'app_label': app_label,
                'db_table': self.db_prefix+PostTermRelationship._meta.db_table,
                'unique_together': (('post', 'taxonomy'),)
            }),
            '_wp_blog': self,
        })
        
        # taxonomy
        # TODO: use a customized manager that maps blog taxonomies and post types
        module.Taxonomy = type('Taxonomy', (Taxonomy,), {
            '__module__': module.__name__,
            'Meta':type('Meta', (Taxonomy.Meta, object),  {
                '__module__': module.__name__,
                'app_label': app_label,
                'db_table': self.db_prefix+Taxonomy._meta.db_table,
                # don't order by taxonomy, as we will usually query individual taxonomies
                'ordering': (
                    'term__name',
                ) if not SUPPORTS_TERM_ORDERING else (
                    'term__order', 'term__name'
                )
            }),
            '_wp_blog': self,
            '_wp_slug_normalizers': dict(
                (k, v['normalize_slug']) for k, v in self.taxonomies.items() if 'normalize_slug' in v
            ),
            '_wp_name_normalizers': dict(
                (k, v['normalize_name']) for k, v in self.taxonomies.items() if 'normalize_name' in v
            ),
        })

        # post meta
        module.PostMeta = type('PostMeta', (PostMeta,), {
            '__module__': module.__name__,
            'Meta':type('Meta', (PostMeta.Meta, object),  {
                '__module__': module.__name__,
                'app_label': app_label,
                'db_table': self.db_prefix+PostMeta._meta.db_table
            }),
            '_wp_blog': self,
        })
        
        # post
        post_attrs = {
            '__module__': module.__name__,
            'Meta':type('Meta', (Post.Meta, object),  {
                '__module__': module.__name__,
                'app_label': app_label,
                'db_table': self.db_prefix+Post._meta.db_table,
            }),
            'objects': managers.PostQuerySet.as_manager(self.post_types.keys()),
            #'categories': property(lambda s: s._filter_taxonomy('category')),
            '_wp_blog': self,
        }
        
        # set properties for single taxonomy types that filter the cached
        # all_taxonomies queryset
        post_types = self.post_types.keys()
        for t_name, t_attrs in self.taxonomies.items():
            if t_attrs['object'] not in post_types:
                continue
            attr_name = t_attrs.get('name', t_name)
            attr_name_plural = t_attrs.get('plural', attr_name+'s')
            #t_name_plural = t_attrs.get('plural', t_name+'s')
            post_attrs[attr_name_plural] = cached_property(named_partial(
                lambda self, taxonomy: self._filter_taxonomy(taxonomy),
                taxonomy=t_name
            ))
            post_attrs[attr_name] = cached_property(named_partial(
                lambda self, taxonomies: self._single_taxonomy(taxonomies),
                taxonomies=attr_name_plural
            ))

        module.Post = type('Post', (Post,), post_attrs)
        
        # comment
        module.Comment = type('Comment', (Comment,), {
            '__module__': module.__name__,
            'Meta':type('Meta', (Comment.Meta, object),  {
                '__module__': module.__name__,
                'app_label': app_label,
                'db_table': self.db_prefix+Comment._meta.db_table
            }),
            '_wp_blog': self,
        })
        
        # comment meta
        module.CommentMeta = type('CommentMeta', (CommentMeta,), {
            '__module__': module.__name__,
            'Meta':type('Meta', (CommentMeta.Meta, object),  {
                '__module__': module.__name__,
                'app_label': app_label,
                'db_table': self.db_prefix+CommentMeta._meta.db_table
            }),
            '_wp_blog': self,
        })

        self.module.models = sys.modules[modname] = module
        
        app_config = RuntimeAppConfig(self.modname, self.module, label=app_label)
        
        apps.app_configs[app_config.label] = app_config
        all_models = apps.all_models[app_config.label]
        app_config.import_models(all_models)
        app_config.ready()
        
        return module
        
        
if SUPPORTS_DOMAIN_MAPPING:
    
    class DomainMapping(models.Model):
        id = models.BigIntegerField(primary_key=True, db_column='ID')
        blog = models.ForeignKey(Blog)
        domain = models.CharField(max_length=255)
        active = models.BooleanField(default=True)
        
        class Meta:
            db_table = DB_PREFIX + 'domain_mapping'
            ordering = ('-active',)
            managed = False


###### blog models


class BlogOption(models.Model):
    id = models.BigIntegerField(primary_key=True, db_column='option_id')
    name = models.CharField(max_length=64, unique=True, db_column='option_name')
    value = models.TextField(db_column='option_value')
    autoload = models.CharField(max_length=20)
    
    class Meta:
        db_table = u'options'
        managed = False
        abstract = True


class TaxonomyTerm(models.Model):
    id = models.BigIntegerField(primary_key=True, db_column='term_id')
    name = models.CharField(max_length=600)
    slug = models.CharField(unique=True, max_length=255)
    group = models.BigIntegerField(db_column='term_group')
    
    objects = managers.TaxonomyTermManager()
    
    class Meta:
        db_table = u'terms'
        managed = False
        abstract = True


class Taxonomy(models.Model):        
    id = models.IntegerField(primary_key=True, db_column='term_taxonomy_id')
    term = models.ForeignKey('TaxonomyTerm', db_column='term_id')
    taxonomy = models.CharField(max_length=96, db_index=True)
    description = models.TextField()
    count = models.BigIntegerField()
    posts = models.ManyToManyField('Post', through='PostTermRelationship')
    
    objects = managers.TaxonomyManager()
    
    class Meta:
        db_table = u'term_taxonomy'
        managed = False
        abstract = True
        unique_together = (('term', 'taxonomy'),)
        ordering = ('term__name',)

    def __init__(self, *args, **kw):
        super(Taxonomy, self).__init__(*args, **kw)
        # ignore WP silly default of 0 instead of NULL
        if self.term_id in (0, '0'):
            self.term_id = None

    @property
    def normalized_slug(self):
        normalizer = self._wp_slug_normalizers.get(self.taxonomy)
        if normalizer is None:
            return self.term.slug
        return normalizer(self.term.slug)
            
    @property
    def normalized_name(self):
        normalizer = self._wp_name_normalizers.get(self.taxonomy)
        if normalizer is None:
            return self.term.name
        return normalizer(self.term.name)
            
    def get_absolute_url(self):
        try:
            return reverse('wpkit_%s' % self.taxonomy, kwargs={'slug':self.normalized_slug})
        except NoReverseMatch:
            #logging.warn("No reverse match for taxonomy type '%s' in blog '%s'" % (self.taxonomy, self._wp_blog))
            return u'/%s/%s/' % (
                self._wp_blog.bases.get(self.taxonomy, self.taxonomy),
                self.term.name
            )
        
    ### cached properties used in templates
            
    @cached_property
    def url(self):
        return self.get_absolute_url()
            
    @cached_property
    def permalink(self):
        return urljoin(self._wp_blog.options.home, self.get_absolute_url())
    

# TODO: add a LinkTermRelationship model for link taxonomies
class PostTermRelationship(models.Model):
    post = models.ForeignKey('Post', db_column='object_id')
    taxonomy = models.ForeignKey('Taxonomy', db_column='term_taxonomy_id')
    order = models.IntegerField(db_column='term_order', primary_key=True)
    
    class Meta:
        db_table = u'term_relationships'
        #ordering = ('taxonomy__term__name', ) #'order',) # unused by wp
        managed = False
        abstract = True

    def __init__(self, *args, **kw):
        super(PostTermRelationship, self).__init__(*args, **kw)
        # ignore WP silly default of 0 instead of NULL
        if self.taxonomy_id in (0, '0'):
            self.taxonomy_id = None
        if self.post_id in (0, '0'):
            self.post_id = None


class Post(models.Model):
    id = models.BigIntegerField(primary_key=True, db_column='ID')
    author = models.ForeignKey('User', db_column='post_author')
    date = models.DateTimeField(db_column='post_date')
    date_gmt = models.DateTimeField(db_column='post_date_gmt')
    title = models.TextField(db_column='post_title')
    content = models.TextField(db_column='post_content')
    excerpt = models.TextField(db_column='post_excerpt')
    status = models.CharField(max_length=60, db_column='post_status')
    comment_status = models.CharField(max_length=60)
    ping_status = models.CharField(max_length=60)
    password = models.CharField(max_length=60, db_column='post_password')
    slug = models.CharField(max_length=600, db_column='post_name')
    #to_ping = models.TextField()
    #pinged = models.TextField()
    modified = models.DateTimeField(db_column='post_modified')
    modified_gmt = models.DateTimeField(db_column='post_modified_gmt')
    content_filtered = models.TextField(db_column='post_content_filtered')
    guid = models.CharField(max_length=765)
    menu_order = models.IntegerField()
    post_type = models.CharField(max_length=60)
    mime_type = models.CharField(max_length=300, db_column='post_mime_type')
    comment_count = models.BigIntegerField()
    parent = models.ForeignKey('self', blank=True, db_column='post_parent', null=True, default=0)
    taxonomies_rel = models.ManyToManyField('Taxonomy', through='PostTermRelationship')
    
    objects = managers.PostQuerySet.as_manager()
    
    class Meta:
        db_table = u'posts'
        managed = False
        abstract = True
        ordering = ('-date',)

    def get_absolute_url(self):
        if self.post_type == 'post':
            return reverse('wpkit_post', kwargs=self.url_args)
        if self.post_type == 'attachment':
            url_args = self.url_args
            url_args['attachment_slug'] = self.slug
            return reverse('wpkit_attachment', kwargs=url_args)
        if self.post_type == 'page':
            return reverse('wpkit_page', kwargs={'slug':self.slug})
        # TODO: give the user the option of customizing the kwargs
        #       with a custom function that accepts the post as input
        try:
            return reverse('wpkit_%s' % self.post_type, kwargs={'slug':self.slug})
        except NoReverseMatch, e:
            logger.critical(e.args)

    @property
    def meta(self):
        return WPPostMeta(self.postmeta_set.values_list('key', 'value'))

    def __init__(self, *args, **kw):
        super(Post, self).__init__(*args, **kw)
        # ignore WP silly default of 0 instead of NULL
        if self.parent_id in (0, '0'):
            self.parent_id = None

    @property
    def url_args(self):
        kw = {}
        for name in self._wp_blog.ps_tokens:
            if name in ('id', 'slug'):
                kw[name] = getattr(self, name)
            elif name in ('year', 'month', 'day', 'hour', 'minute', 'second'):
                kw[name] = self.date.strftime('%'+{
                    'year':'Y', 'month':'m', 'day':'d',
                    'hour':'H', 'minute':'M', 'second':'S'
                }[name])
            elif name in ('category', 'tag'):
                for t in self.taxonomies:
                    if t.taxonomy == name:
                        kw[name] = t.term.name
                        break
            elif name == 'author':
                kw[name] = self.author.nicename or self.author.login
        return kw
            
    @cached_property
    def taxonomies(self):
        # use the queryset cache
        return self.taxonomies_rel.all()

    def _filter_taxonomy(self, taxonomy):
        return [t for t in self.taxonomies if t.taxonomy == taxonomy]
    
    def _single_taxonomy(self, taxonomies):
        try:
            return getattr(self, taxonomies)[0]
        except IndexError:
            pass

    ### content methods and properties
    
    # How we deal with excerpt:
    # 
    # * if all you need is the raw excerpt from the database use post.excerpt
    #
    # * if you need an excerpt even if the user has not defined one,
    #   use auto_excerpt: if one has been set you'll get it, if not you'll
    #   get an auto-generated one
    #
    # How we deal with content:
    #
    # * if all you need is the raw content from the database use post.content
    #
    # * if you need to know if the post has a leader (i.e. if the More tag
    #   has been used), check post.has_more
    #
    # * in posts lists (e.g. the home page) you usually want a leader if one
    #   has been defined, the full post content otherwise; post.content_leader
    #   will give you the unformatted leader
    #
    # * in the post page, you usually need to show the full content if no leader
    #   is set, the leader + more anchor + trailer if a leader is set; use
    #   post.content_leader and post.has_more to decide whether to show an anchor,
    #   and post.content_trailer which will be null if no More tag has been used
    #
    # No formatting (balance tags, texturize, autop, shortcodes) is applied to
    # the excerpt or content. Formatting is done through accessory functions,
    # which are also wrapped in template filters.
    # 
    # In code:
    # 
    #     format_content(post.content_leader)
    #
    # In templates:
    #
    #     {{post.content_leader|format_content}}
    #
    # If you are using preformatting with the WP plugin (you should), a function
    # and corresponfing template filter check if the preformatted data exists
    # and is valid, alternatively returning the formatted raw data. If you need
    # to use a different formatting pipeline create a new template filter
    # library, using the get_part function and wrapping your formatting calls
    # around it.
    # 
    # In code:
    #
    #     formatted_part(post, 'leader')
    #
    # In templates:
    #
    #     {{post|formatted_part:"leader"}}
    #
    
    def _bootstrap_content(self):
        if not hasattr(self, '_has_more'):
            m = POST_MORE_RE.search(self.content)
            if not m:
                self._has_more = False
                self._content_leader = self.content
                self._content_trailer = None
            else:
                self._has_more = True
                self._content_leader = self.content[:m.start()]
                self._content_trailer = self.content[m.end():]
    
    @property
    def has_more(self):
        """Returns True if the post content is split wuth the More tag."""
        self._bootstrap_content()
        return self._has_more
    
    @property
    def content_leader(self):
        """Returns the content up to the More tag if it has been used,
        the full content if the More tag has not been used.
        """
        self._bootstrap_content()
        return self._content_leader
    
    @property
    def content_trailer(self):
        """Returns the content from the More tag to the end if the More tag
        has been used, None if no More tag has been used.
        """
        self._bootstrap_content()
        return self._content_trailer
    
    ### cached properties used in templates
            
    @cached_property
    def url(self):
        return self.get_absolute_url()
            
    @cached_property
    def permalink(self):
        return urljoin(self._wp_blog.options.home, self.get_absolute_url())
    

class PostMeta(models.Model):
    id = models.BigIntegerField(primary_key=True, db_column='meta_id')
    post = models.ForeignKey('Post')
    key = models.CharField(max_length=765, db_column='meta_key')
    value = models.TextField(db_column='meta_value')
    
    class Meta:
        db_table = 'postmeta'
        managed = False
        abstract = True

     
class Comment(models.Model):
    id = models.AutoField(primary_key=True, db_column='comment_ID')
    post = models.ForeignKey('Post', db_column='comment_post_ID')
    author = models.TextField(db_column='comment_author')
    author_email = models.CharField(max_length=300, db_column='comment_author_email')
    author_url = models.CharField(max_length=600, db_column='comment_author_url', blank=True, default='')
    author_ip = models.CharField(max_length=300, db_column='comment_author_IP')
    date = models.DateTimeField(db_column='comment_date', blank=True, default=datetime.datetime.now)
    date_gmt = models.DateTimeField(db_column='comment_date_gmt', blank=True, default=datetime.datetime.utcnow)
    content = models.TextField(db_column='comment_content') # TODO: find a place where to store the parsed content
    karma = models.IntegerField(db_column='comment_karma', blank=True, default=0)
    approved = models.CharField(max_length=60, db_column='comment_approved')
    agent = models.CharField(max_length=765, db_column='comment_agent')
    comment_type = models.CharField(max_length=60, default='')
    parent = models.ForeignKey('self', blank=True, db_column='comment_parent', null=True, default=0)
    user = models.ForeignKey(User, blank=True, null=True, default=0)
    
    objects = managers.CommentQuerySet.as_manager()
    
    class Meta:
        db_table = u'comments'
        ordering = ('date', 'id')
        managed = False
        abstract = True

        
class CommentMeta(models.Model):
    id = models.BigIntegerField(primary_key=True, db_column='meta_id')
    comment = models.ForeignKey('Comment')
    name = models.CharField(max_length=765, blank=True, db_column='meta_key')
    value = models.TextField(blank=True, db_column='meta_value')
    
    class Meta:
        db_table = u'commentmeta'
        managed = False
        abstract = True
