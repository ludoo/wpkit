import os
import re
import time
import datetime

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.db import models
from django.utils.safestring import mark_safe

from wp_frontman.models import Site, Blog
from wp_frontman.managers import *
from wp_frontman.lib.utils import pluralize
from wp_frontman.lib.wp_tagsoup import convert as convert_wp_tagsoup
from wp_frontman.lib.wp_shortcodes import gallery as gallery_shortcode
from wp_frontman.lib.external.phpserialize import loads as php_unserialize


class WPModelMixin(object):
    
    wp_site = None
    wp_blog = None
    _wp_model_scope = dict(blog=5)
    
    @classmethod
    def _wp_model_attrs(cls, wp_container, mod_name, class_name, extra_meta_attrs=None):
        meta_attrs = dict(
            __module__=mod_name,
            db_table=wp_container.db_prefix+cls.Meta.db_table,
            app_label=mod_name
        )
        if isinstance(extra_meta_attrs, dict):
            meta_attrs.update(extra_meta_attrs)
        attrs = dict(
            __module__=mod_name,
            Meta=type('Meta', (cls.Meta, object), meta_attrs)
        )
        if isinstance(wp_container, Blog):
            attrs['wp_blog'] = wp_container
        elif isinstance(wp_container, Site):
            attrs['wp_site'] = wp_container
        else:
            raise TypeError("Unknown wp container '%s' for '%s'" % (wp_container, cls))
        return attrs
    
    @classmethod
    def _wp_model_factory(cls, wp_container, mod, manager_db=None, class_name=None, extra_attrs=None):
        mod_name = mod.__name__
        class_name = class_name or cls.__name__
        attrs = cls._wp_model_attrs(wp_container, mod_name, class_name)
        if isinstance(extra_attrs, dict):
            attrs.update(extra_attrs)
        _cls = type(class_name, (cls,), attrs)
        if manager_db:
            _cls.objects._db = manager_db
        setattr(mod, class_name, _cls)
        return _cls
    
    @classmethod
    def _wp_proxy_model_factory(cls, proxied, wp_container, mod, manager_db=None, class_name=None, extra_attrs=None):
        mod_name = mod.__name__
        class_name = class_name or cls.__name__
        attrs = dict(
            __module__=mod_name,
            wp_blog=wp_container,
            Meta=type('Meta', (proxied.Meta, object), dict(
                __module__=mod_name,
                app_label=mod_name,
                proxy=True
            ))
        )
        if isinstance(extra_attrs, dict):
            attrs.update(extra_attrs)
        _cls = type(class_name, (proxied,), attrs)
        if manager_db:
            _cls.objects._db = manager_db
        setattr(mod, class_name, _cls)
        return _cls


class User(WPModelMixin, models.Model):
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
    
    #objects = UserManager()
    
    class Meta:
        db_table = u'users'
        managed = False
        abstract = True
        
    def __init__(self, *args, **kw):
        super(User, self).__init__(*args, **kw)
        self._meta = None
        
    @property
    def meta(self):
        if self._meta is None:
            self._meta = list(self.usermeta_set.select_related('user').all())
        return self._meta
        
    def __unicode__(self):
        return u"%s id %s status %s" % (self.login, self.id, self.status)
    
    _wp_model_scope = dict(site=5)
    
    @classmethod
    def _wp_model_factory(cls, wp_container, mod, manager_db=None, class_name=None, extra_attrs=None):
        if isinstance(wp_container, Site):
            return super(User, cls)._wp_model_factory(wp_container, mod, manager_db, class_name, extra_attrs)
        return cls._wp_proxy_model_factory(wp_container.site.models.User, wp_container, mod, manager_db, class_name, extra_attrs)
    
    
class UserMeta(WPModelMixin, models.Model):
    user = models.ForeignKey('User')
    id = models.BigIntegerField(primary_key=True, db_column='umeta_id')
    name = models.CharField(max_length=765, blank=True, db_column='meta_key')
    value = models.TextField(blank=True, db_column='meta_value')
    
    class Meta:
        db_table = u'usermeta'
        managed = False
        abstract = True

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
        
    _wp_model_scope = dict(site=5)
    
    @classmethod
    def _wp_model_factory(cls, wp_container, mod, manager_db=None, class_name=None, extra_attrs=None):
        if isinstance(wp_container, Site):
            return super(UserMeta, cls)._wp_model_factory(wp_container, mod, manager_db, class_name, extra_attrs)
        return cls._wp_proxy_model_factory(wp_container.site.models.UserMeta, wp_container, mod, manager_db, class_name, extra_attrs)


class TaxonomyTerm(WPModelMixin, models.Model):
    id = models.BigIntegerField(primary_key=True, db_column='term_id')
    name = models.CharField(max_length=600)
    slug = models.CharField(unique=True, max_length=255)
    group = models.BigIntegerField(db_column='term_group')
    
    class Meta:
        db_table = u'terms'
        managed = False
        abstract = True
        ordering = ('name',)
        
    def __unicode__(self):
        return u"%s id %s" % (self.slug, self.id)
    
    _wp_model_scope = dict(blog=1)
    
    @classmethod
    def _wp_model_attrs(cls, blog, *args, **kw):
        if blog.site.meta['wp_frontman']['support_category_order']:
            kw['extra_meta_attrs'] = dict(ordering=('order', 'name'))
        attrs = super(TaxonomyTerm, cls)._wp_model_attrs(blog, *args, **kw)
        if blog.site.meta['wp_frontman']['support_category_order']:
            attrs['order'] = models.IntegerField(db_column='term_order', db_index=True)
        return attrs
    

def _new_taxonomy(cls, *args, **kw):
    """partial inspiration from here
    http://stackoverflow.com/questions/2542157/subclassed-django-models-with-integrated-querysets
    """
    if 'taxonomy' in kw:
        taxonomy = kw['taxonomy']
    elif args:
        taxonomy = args[1]
    else:
        taxonomy = None
    
    _cls = cls._wp_taxonomy_for_type.get(taxonomy, cls)
    
    obj = super(_cls, _cls).__new__(_cls) #, *args, **kw)
    
    # hack
    if not getattr(_cls, '_wp_taxonomy_hierarchical', False):
        if kw and 'parent_id' in kw:
            del kw['parent_id']
        elif len(args) == 6:
            args = args[:4] + args[5:]

    if _cls != cls:
        obj.__init__(*args, **kw)
    return obj

        
class Taxonomy(WPModelMixin, models.Model):
    id = models.IntegerField(primary_key=True, db_column='term_taxonomy_id')
    #term = models.ForeignKey('TaxonomyTerm', db_column='term_id', unique=True)
    taxonomy = models.CharField(max_length=96, db_index=True)
    description = models.TextField()
    count = models.BigIntegerField()
    
    objects = filtered_manager_factory('TaxonomyManager', dict(), bases=(TaxonomyManagerMixin, models.Manager))()
    
    class Meta:
        db_table = u'term_taxonomy'
        managed = False
        abstract = True
        unique_together = (('term', 'taxonomy'),)
        ordering = ('term__name',)
        
    def __init__(self, *args, **kw):
        super(Taxonomy, self).__init__(*args, **kw)
        if getattr(self, '_wp_taxonomy_hierarchical', False):
            if self.parent_id in (0, '0'):
                self.parent_id = None
        
    def get_absolute_url(self):
        return '### Taxonomy.get_absolute_url() has not been implemented yet ###'
        
    def __repr__(self):
        return "<%s '%s' id %s>" % (self.__class__.__name__, self.taxonomy, self.id)
    
    def __unicode__(self):
        return repr(self)
        
    _wp_model_scope = dict(blog=2)
    
    @classmethod
    def _wp_model_attrs(cls, wp_container, mod_name, class_name, extra_meta_attrs=None):
        attrs = super(Taxonomy, cls)._wp_model_attrs(wp_container, mod_name, class_name, extra_meta_attrs)
        attrs['term'] = models.ForeignKey('TaxonomyTerm', db_column='term_id', unique=True)
        return attrs
    
    @classmethod
    def _wp_model_factory(cls, blog, mod, manager_db=None):
        generic_taxonomy = super(Taxonomy, cls)._wp_model_factory(blog, mod, manager_db, class_name=None, extra_attrs=dict(
            parent=models.ForeignKey('Taxonomy', blank=True, null=True, db_column='parent', to_field='term'),
            _wp_taxonomy_for_model=dict(), _wp_taxonomy_for_type=dict(),
            _wp_taxonomy_types=list(), _wp_taxonomy_object_types=None
        ))
        generic_taxonomy.__new__ = staticmethod(_new_taxonomy)
        return generic_taxonomy
    
    @classmethod
    def _wp_object_taxonomy_factory(cls, model_name, object_types, blog, mod, manager_db):
        generic_taxonomy = mod.Taxonomy
        _ot = set(object_types)
        taxonomies = [k if isinstance(k, str) else str(k) for k, v in blog.taxonomies.items() if set(v['object_type'].values()).intersection(_ot)]
        model_taxonomy = super(Taxonomy, cls)._wp_proxy_model_factory(
            generic_taxonomy, blog, mod, manager_db, model_name + 'Taxonomy', extra_attrs=dict(
                objects=filtered_manager_factory(
                    model_name+'TaxonomyManager',
                    dict(taxonomy__in=taxonomies), bases=(TaxonomyManagerMixin, models.Manager)
                )(),
                _wp_taxonomy_object_types=object_types,
                _wp_taxonomy_types=taxonomies,
                _wp_taxonomy_generic_name='Taxonomy'
            )
        )
        model_taxonomy.__new__ = staticmethod(_new_taxonomy)
        generic_taxonomy._wp_taxonomy_for_model[model_name] = model_taxonomy
        return model_taxonomy
    
    @classmethod
    def _wp_taxonomy_factory(cls, model_name, object_type, blog, mod, manager_db):
        generic_taxonomy = mod.Taxonomy
        taxonomies = list()
        for taxonomy, data in blog.taxonomies.items():
            if object_type not in data['object_type'].values():
                continue
            taxonomy = taxonomy if isinstance(taxonomy, str) else str(taxonomy)
            if taxonomy in generic_taxonomy._wp_taxonomy_for_type:
                taxonomies.append(generic_taxonomy._wp_taxonomy_for_type[taxonomy])
                continue
            taxonomy_name = taxonomy.replace('_', ' ').title().replace(' ', '')
            extra_attrs = dict(
                objects=filtered_manager_factory(taxonomy_name+'Manager', dict(taxonomy=taxonomy), bases=(TaxonomyManagerMixin, models.Manager))(),
                _wp_taxonomy_object_types=data['object_type'].values(),
                _wp_taxonomy_types=[taxonomy],
                _wp_taxonomy_hierarchical=data['hierarchical'],
                _wp_taxonomy_name=taxonomy
            )
            if data['hierarchical']:
                extra_attrs['parent'] = models.ForeignKey(taxonomy_name, blank=True, null=True, db_column='parent', to_field='term')
            taxonomy_model = super(Taxonomy, cls)._wp_model_factory(blog, mod, manager_db, taxonomy_name, extra_attrs)
            generic_taxonomy._wp_taxonomy_for_type[taxonomy] = taxonomy_model
            generic_taxonomy._wp_taxonomy_types.append(taxonomy)
            taxonomies.append(taxonomy_model)
        return taxonomies
    
    @classmethod
    def _wp_taxonomy_rel_factory(cls, model_name, taxonomy_class, blog, mod, manager_db, object_type_field=None, model_relname='+', taxonomy_relname='+'):
        rel_name = model_name + 'Rel' + getattr(taxonomy_class, '_wp_taxonomy_generic_name', taxonomy_class.__name__)
        rel_attrs = {
            model_name.lower()      : models.ForeignKey(model_name, db_column='object_id', primary_key=True, related_name=model_relname),
            'taxonomy'              : models.ForeignKey(taxonomy_class, db_column='term_taxonomy_id', primary_key=True, related_name=taxonomy_relname)
        }
        from django.db.models.loading import get_apps, get_models, get_model
        manager_attrs = dict(
            taxonomy__taxonomy__in = taxonomy_class._wp_taxonomy_types,
        )
        if object_type_field is not None and taxonomy_class._wp_taxonomy_object_types:
            manager_attrs[model_name.lower() + '__' + object_type_field + '__in'] = taxonomy_class._wp_taxonomy_object_types
        rel_attrs['objects'] = filtered_manager_factory(rel_name + 'Manager', manager_attrs)()
        return TermRelationship._wp_model_factory(blog, mod, manager_db, rel_name, extra_attrs=rel_attrs)
        

class TermRelationship(WPModelMixin, models.Model):
    #post = models.ForeignKey(Post, db_column='object_id')
    #taxonomy = models.ForeignKey(TermTaxonomy, limit_choices_to=dict(taxonomy='category'), db_column='term_taxonomy_id')
    order = models.IntegerField(db_column='term_order')
    
    class Meta:
        db_table = u'term_relationships'
        ordering = ('taxonomy__term__name', ) #'order',) # unused by wp
        managed = False
        abstract = True
        
    _wp_model_scope = dict()
    
    @classmethod
    def _wp_model_attrs(cls, blog, *args, **kw):
        if blog.site.meta['wp_frontman']['support_category_order']:
            kw['extra_meta_attrs'] = dict(ordering=('taxonomy__term__order', 'taxonomy__term__name'))
        attrs = super(TermRelationship, cls)._wp_model_attrs(blog, *args, **kw)
        return attrs
    

def _new_post_type(cls, *args, **kw):
    """partial inspiration from here
    http://stackoverflow.com/questions/2542157/subclassed-django-models-with-integrated-querysets
    """
    if 'post_type' in kw:
        post_type = kw['post_type']
    elif args:
        pos = getattr(cls, '_basepost_post_type_pos', None)
        if pos is None:
            pos = [i for i, f in enumerate(cls._meta.fields) if f.name == 'post_type'][0]
            cls._basepost_post_type_pos = pos
        post_type = args[cls._basepost_post_type_pos]
    else:
        post_type = None
    _cls = cls._wp_post_types.get(post_type, cls)
    
    obj = super(_cls, _cls).__new__(_cls) #, *args, **kw)
    if _cls != cls:
        obj.__init__(*args, **kw)
    return obj


class BasePost(WPModelMixin, models.Model):
    
    id = models.BigIntegerField(primary_key=True, db_column='ID')
    #author = models.ForeignKey('User', db_column='post_author')
    date = models.DateTimeField(db_column='post_date')
    date_gmt = models.DateTimeField(db_column='post_date_gmt')
    content = models.TextField(db_column='post_content')
    title = models.TextField(db_column='post_title')
    _excerpt = models.TextField(db_column='post_excerpt')
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
    #parent = models.ForeignKey('BasePost', blank=True, db_column='post_parent', null=True, default=0)
    #base_taxonomy = models.ManyToManyField('TaxonomyTerm', through='PostTerms')
    #tags = models.ManyToManyField('PostTag', through='PostTags')
    
    objects = BasePostManager()

    class Meta:
        db_table = u'posts'
        managed = False
        abstract = True
        ordering = ('-date',)
    
    def __init__(self, *args, **kw):
        super(BasePost, self).__init__(*args, **kw)
        ### ignore WP fucked-up defaults of 0 instead of NULL
        if self.parent_id in (0, '0'):
            self.parent_id = None

    ### permalinks

    # map wordpress permalink tokens to properties
    
    year = property(lambda s: s.date.year)
    month = property(lambda s: "%02d" % s.date.month)
    day = property(lambda s: "%02d" % s.date.day)
    hour = property(lambda s: "%02d" % s.date.hour)
    minute = property(lambda s: "%02d" % s.date.minute)
    second = property(lambda s: "%02d" % s.date.second)
    
    _permalink_tokens = tuple(Blog.wp_permalink_map.get(k, k) for k in Blog.wp_permalink_tokens)

    @property
    def permalink_tokens(self):
        if self.post_type != 'post':
            return dict()
        blog_tokens = self.wp_blog.options['permalink_tokens']
        tokens = dict()
        for k in self._permalink_tokens:
            if not k in blog_tokens:
                continue
            v = getattr(self, k)
            tokens[k] = v if not hasattr(v, 'permalink_token') else v.permalink_token
        return tokens

    def get_absolute_url(self):
        if not hasattr(self, '_absolute_url'):
            if self.post_type == 'page':
                url = reverse('wpf_index')
                if not url.endswith('/'):
                    url += '/'
                url += self.slug
                if getattr(settings, 'APPEND_SLASH', False):
                    url += '/'
            else:
                url = reverse('wpf_post', kwargs=self.permalink_tokens)
            self._absolute_url = url
        return self._absolute_url
    
    @property
    def permalink(self):
        return urljoin(Blog.get_active().home, self.get_absolute_url())

        
    _excerpt_stripper_re = re.compile(r'(?smu)(?:<style[^>]*>.*?</style>)|(?:</?[^>]+>)')
    _space_splitter_re = re.compile(r'(?smu)\s+')

    @property
    def excerpt(self):
        if self._excerpt:
            return self._excerpt
        # TODO: pay more attention to entities, comments, etc.
        if not self.content:
            return ''
        tokens = self._space_splitter_re.split(self._excerpt_stripper_re.sub('', self.content_parsed).replace('&nbsp;', ' '))
        if len(tokens) > 45:
            tokens = tokens[:45]
        return u' '.join(tokens).replace("\n\n", "</p>\n<p>").strip()
        
    @property
    def content_stripped(self):
        return strip_html(self.content)
    
    @property
    def more(self):
        if not hasattr(self, '_content_data'):
            self._bootstrap_content()
        return self._content_data['has_more']

    @property
    def summary(self):
        if not hasattr(self, '_content_data'):
            self._bootstrap_content()
        return self._content_data['summary']
    
    @property
    def content_parsed(self):
        if not hasattr(self, '_content_data'):
            self._bootstrap_content()
        return mark_safe(self._content_data['content_parsed'])
        
    @property
    def summary_parsed(self):
        if not hasattr(self, '_content_data'):
            self._bootstrap_content()
        return mark_safe(self._content_data['summary_parsed'])
    
    _more_re = re.compile(r'(?smu)<!--more[^>]?-->')
    
    def _bootstrap_content(self):
        summary = content = summary_parsed = content_parsed = ''
        more = False
        tstamp = None
        content = self.content.strip()
        if content:
            m = self._more_re.search(content)
            if m:
                summary = content[:m.start()]
                more = True
            if self.content_filtered:
                try:
                    summary_parsed, content_parsed, tstamp = self.content_filtered.split(chr(0))
                    tstamp = int(tstamp)
                except (TypeError, ValueError):
                    pass
            if not tstamp or int(time.mktime(self.modified_gmt.timetuple())) != tstamp:
                # no preformatted content, WP shortcodes won't work (yet)
                summary_parsed = '' if not summary else convert_wp_tagsoup(summary)
                content_parsed = convert_wp_tagsoup(content)
            if summary:
                content_parsed = self._more_re.sub('<span id="more-%s"></span>' % self.id, content_parsed)
        self._content_data = dict(
            summary=summary or content, content=content,
            summary_parsed=summary_parsed or content_parsed,
            content_parsed=content_parsed, has_more=more
        )
    
    ### prefetch properties
    
    @property
    def metadict(self):
        if not hasattr(self, '_metadict'):
            if not hasattr(self, 'wp_prefetched_postmeta'):
                self.wp_prefetched_postmeta = list(self.postmeta_set.all())
            self._metadict = dict(m.parsed() for m in self.wp_prefetched_postmeta)
        return self._metadict
    
    @property
    def meta(self):
        if not hasattr(self, 'wp_prefetched_postmeta'):
            self.wp_prefetched_postmeta = list(self.postmeta_set.all())
        return self.wp_prefetched_postmeta
    
    @property
    def taxonomies(self):
        if not hasattr(self, 'wp_prefetched_taxonomies'):
            self.wp_prefetched_taxonomies = list(self.wp_taxonomyrel_set.select_related('taxonomy'))
        return [r.taxonomy for r in self.wp_prefetched_taxonomies]
    
    @property
    def children(self):
        if not hasattr(self, 'wp_prefetched_children'):
            self.wp_prefetched_children = list(self.wp_blog.models.BasePost.objects.filter(parent=self).prefetch_postmeta())
        return self.wp_prefetched_children

    @property
    def attachments(self):
        if not hasattr(self, 'wp_prefetch_attachments'):
            if hasattr(self, 'wp_prefetched_children'):
                self.wp_prefetch_attachments = [c for c in self.children if c.post_type == 'attachment']
            else:
                self.wp_prefetch_attachments = list(
                    self.wp_blog.models.BasePost.objects.filter(parent=self, post_type='attachment').prefetch_postmeta()
                )
        return self.wp_prefetch_attachments
    
    @property
    def image_attachments(self):
        if not hasattr(self, 'wp_prefetched_image_attachments'):
            if hasattr(self, 'wp_prefetch_attachments'):
                self.wp_prefetched_image_attachments = [c for c in self.wp_prefetch_attachments if c.mime_type.startswith('image/')]
            elif hasattr(self, 'wp_prefetched_children'):
                self.wp_prefetched_image_attachments = [c for c in self.children if c.post_type == 'attachment' and c.mime_type.startswith('image/')]
            else:
                self.wp_prefetched_image_attachments = list(
                    self.wp_blog.models.BasePost.objects.filter(
                        parent=self, post_type='attachment', mime_type__startswith='image/'
                    ).prefetch_postmeta()
                )
        return self.wp_prefetched_image_attachments
    
    ### image properties
    
    @property
    def attached_file(self):
        return self.metadict.get('attached_file')
    
    @property
    def attachment_metadata(self):
        return self.metadict.get('attachment_metadata')
    
    _gallery_cmp = staticmethod(lambda a, b: cmp(a.menu_order or a.id, b.menu_order or b.id))
    
    @property
    def gallery_images(self):
        # TODO: implement all other gallery options
        gallery = gallery_shortcode(self.content)
        if gallery is None:
            return
        if 'ids' not in gallery:
            return self.image_attachments
        ids = [int(i) for i in gallery['ids'].split(',')]
        print self._gallery_cmp, self._gallery_cmp(self.image_attachments[0], self.image_attachments[1])
        return sorted([a for a in self.image_attachments if a.id in ids], cmp=self._gallery_cmp)
        
    @property
    def featured_image(self):
        if not hasattr(self, 'wp_prefetched_featured_image'):
            if '_thumbnail_id' not in self.metadict:
                self.wp_prefetched_featured_image = None
                return
            try:
                self.wp_prefetched_featured_image = self.wp_blog.models.BasePost.objects.get(id=self.metadict['_thumbnail_id'])
            except type(self).DoesNotExist:
                self.wp_prefetched_featured_image = None
        return self.wp_prefetched_featured_image
    
    _wp_post_type = None
    
    @classmethod
    def _wp_model_factory(cls, blog, mod, manager_db=None, class_name=None):
        
        # base post
        extra_attrs = dict(
            author=models.ForeignKey(blog.site.models.User, db_column='post_author'),
            parent=models.ForeignKey('BasePost', blank=True, db_column='post_parent', null=True, default=0),
            _wp_post_types = dict()
        )
        generic_taxonomy = Taxonomy._wp_object_taxonomy_factory(
            'BasePost', blog.post_types.keys(), blog, mod, manager_db
        )
        taxonomy_rel = Taxonomy._wp_taxonomy_rel_factory(
            'BasePost', generic_taxonomy, blog, mod, manager_db, 'post_type',
            model_relname='wp_taxonomyrel_set', taxonomy_relname='wp_basepostrel_set'
        )
        extra_attrs['wp_taxonomies'] = models.ManyToManyField(generic_taxonomy, through=taxonomy_rel)
        base_post = super(BasePost, cls)._wp_model_factory(blog, mod, manager_db, class_name, extra_attrs=extra_attrs)
        base_post.__new__ = staticmethod(_new_post_type)

        # specific post types
        def _taxonomies_getter(name):
            def func(self):
                return [t for t in self.taxonomies if t.taxonomy == name]
            return func 
        
        def _taxonomy_getter(names):
            def func(self):
                try:
                    return getattr(self, names)[0]
                except IndexError:
                    pass
            return func
        
        for post_type, post_data in blog.post_types.items():
            if isinstance(post_type, unicode):
                post_type = str(post_type)
            _class_name = post_type.replace('_', ' ').title().replace(' ', '')
            objects = filtered_manager_factory(_class_name+'Manager', dict(post_type=post_type), bases=(BasePostManager,))()
            extra_attrs = dict(
                objects=objects,
                author=models.ForeignKey(blog.site.models.User, db_column='post_author', related_name='post_set_%s' % blog.blog_id),
                parent=models.ForeignKey('BasePost', blank=True, db_column='post_parent', null=True, default=0),
                _wp_post_type=post_type, _wp_post_type_attrs=post_data,
            )
            #if post_data['hierarchical']:
            #    extra_attrs['parent'] = models.ForeignKey('BasePost', blank=True, db_column='post_parent', null=True, default=0)
            #elif post_type != 'post':
                # parent can refer to a related post instead of a hierarchical parent, eg for attachments and revisions,
                # but only if it's not a post
            #    extra_attrs['parent'] = models.ForeignKey('BasePost', blank=True, db_column='post_parent', null=True, default=0)
            #else:
            #    extra_attrs['parent_id'] = None
            #    extra_attrs['parent'] = None
            taxonomy_rel = Taxonomy._wp_taxonomy_rel_factory(
                _class_name, generic_taxonomy, blog, mod, manager_db, 'post_type',
                model_relname='wp_taxonomyrel_set', taxonomy_relname='wp_' + post_type + 'rel_set'
            )
            extra_attrs['wp_taxonomies'] = models.ManyToManyField(generic_taxonomy, through=taxonomy_rel)
            #for taxonomy_name, taxonomy_data in blog.taxonomies.items():
            #    if post_type not in taxonomy_data['object_type'].values():
            #        continue
            for taxonomy in Taxonomy._wp_taxonomy_factory(_class_name, post_type, blog, mod, manager_db):
                t_name = taxonomy._wp_taxonomy_name
                t_name_plural = pluralize(t_name)
                taxonomy_rel = Taxonomy._wp_taxonomy_rel_factory(_class_name, taxonomy, blog, mod, manager_db, 'post_type')
                extra_attrs['wp_' + t_name_plural] = models.ManyToManyField(taxonomy, through=taxonomy_rel)
                extra_attrs[t_name_plural] = property(
                    _taxonomies_getter(t_name), None, None,
                    "Return taxonomy objects of type '%s' for this model, using the related cache if available." % t_name
                )
                extra_attrs[t_name] = property(
                    _taxonomy_getter(t_name_plural), None, None,
                    "Return the first taxonomy object of type '%s' for this model, using the related cache if available." % t_name
                )
            base_post._wp_post_types[post_type] = super(BasePost, cls)._wp_model_factory(blog, mod, manager_db, _class_name, extra_attrs)
            

class PostMeta(WPModelMixin, models.Model):
    id = models.BigIntegerField(primary_key=True, db_column='meta_id')
    #post = models.ForeignKey('BasePost')
    name = models.CharField(max_length=765, db_column='meta_key')
    value = models.TextField(db_column='meta_value')
    
    class Meta:
        db_table = 'postmeta'
        abstract = True
    
    def parsed(self):
        if self.name == '_wp_attached_file':
            return ('attached_file', self.wp_blog.options['fileupload_path'] + self.value)
        if self.name == '_wp_attachment_metadata':
            data = php_unserialize(self.value)
            if data['file']:
                data['url'] = self.wp_blog.options['fileupload_path'] + data['file']
                base = os.path.dirname(data['url'])
            if isinstance(data.get('sizes'), dict):
                for k, v in data['sizes'].items():
                    if 'file' in v:
                        v['url'] = base + '/' + v['file']
            return ('attachment_metadata', data)
        return (self.name, self.value)
        
    _wp_model_scope = dict(blog=11)
    
    @classmethod
    def _wp_model_attrs(cls, wp_container, mod_name, class_name, extra_meta_attrs=None):
        attrs = super(PostMeta, cls)._wp_model_attrs(wp_container, mod_name, class_name, extra_meta_attrs)
        attrs['post'] = models.ForeignKey('BasePost')
        return attrs
    
    @classmethod
    def _wp_model_factory(cls, blog, mod, manager_db=None, class_name=None):
        model = super(PostMeta, cls)._wp_model_factory(blog, mod, manager_db, class_name)
        # hack alert
        for post_type, post_model in mod.BasePost._wp_post_types.items():
            post_model.postmeta_set = mod.BasePost.postmeta_set
        return model


class Link(WPModelMixin, models.Model):
    id = models.BigIntegerField(primary_key=True, db_column='link_id')
    url = models.CharField(max_length=765, db_column='link_url')
    name = models.CharField(max_length=765, db_column='link_name')
    image = models.CharField(max_length=765, db_column='link_image')
    target = models.CharField(max_length=75, db_column='link_target')
    description = models.CharField(max_length=765, db_column='link_description')
    visible = models.CharField(max_length=60, db_column='link_visible')
    #owner = models.BigIntegerField(db_column='link_owner')
    rating = models.IntegerField(db_column='link_rating')
    updated = models.DateTimeField(db_column='link_updated')
    rel = models.CharField(max_length=765, db_column='link_rel')
    notes = models.TextField(db_column='link_notes')
    rss = models.CharField(max_length=765, db_column='link_rss')
    #categories = models.ManyToManyField('LinkCategory', through='LinkCategories')    
    
    objects = LinkManager()
    
    class Meta:
        db_table = 'links'
        abstract = True

    @classmethod
    def _wp_model_factory(cls, blog, mod, manager_db=None, class_name=None):
        class_name = class_name or cls.__name__
        extra_attrs = dict()
        generic_taxonomy = Taxonomy._wp_object_taxonomy_factory(class_name, ['link'], blog, mod, manager_db)
        taxonomy_rel = Taxonomy._wp_taxonomy_rel_factory(class_name, generic_taxonomy, blog, mod, manager_db)
        extra_attrs['wp_taxonomies'] = models.ManyToManyField(generic_taxonomy, through=taxonomy_rel)
        for taxonomy in Taxonomy._wp_taxonomy_factory(class_name, 'link', blog, mod, manager_db):
            taxonomy_rel = Taxonomy._wp_taxonomy_rel_factory(class_name, taxonomy, blog, mod, manager_db)
            extra_attrs['wp_' + pluralize(taxonomy.__name__)] = models.ManyToManyField(taxonomy, through=taxonomy_rel)
        return super(Link, cls)._wp_model_factory(blog, mod, manager_db, class_name, extra_attrs)
   

class Comment(WPModelMixin, models.Model):
    id = models.AutoField(primary_key=True, db_column='comment_ID')
    #base_post = models.ForeignKey('BasePost', db_column='comment_post_ID')
    author = models.TextField(db_column='comment_author')
    author_email = models.CharField(max_length=300, db_column='comment_author_email')
    author_url = models.CharField(max_length=600, db_column='comment_author_url', blank=True, default='')
    author_ip = models.CharField(max_length=300, db_column='comment_author_IP')
    date = models.DateTimeField(db_column='comment_date', blank=True, default=datetime.datetime.now)
    date_gmt = models.DateTimeField(db_column='comment_date_gmt', blank=True, default=datetime.datetime.utcnow)
    rawcontent = models.TextField(db_column='comment_content') # TODO: find a place where to store the parsed content
    karma = models.IntegerField(db_column='comment_karma', blank=True, default=0)
    approved = models.CharField(max_length=60, db_column='comment_approved')
    agent = models.CharField(max_length=765, db_column='comment_agent')
    comment_type = models.CharField(max_length=60, default='')
    #parent = models.ForeignKey('BaseComment', blank=True, db_column='comment_parent', null=True, default=0)
    #user = models.ForeignKey(User, blank=True, null=True, default=0)
    
    objects = CommentManager()
    
    class Meta:
        db_table = u'comments'
        ordering = ('date', 'id') # if getattr(blog, 'comment_order', None) == 'asc' else ('-date', '-id')
        managed = False
        abstract = True

    _wp_model_scope = dict(blog=10)

    @classmethod
    def _wp_model_factory(cls, blog, mod, manager_db=None, class_name=None):
        base_post = mod.BasePost
        extra_attrs = dict(
            post=models.ForeignKey(base_post, db_column='comment_post_ID', related_name='comment_set'),
            parent=models.ForeignKey('Comment', blank=True, db_column='comment_parent', null=True, default=0),
            user=models.ForeignKey(blog.site.models.User, blank=True, null=True, default=0),
        )
        base_comment = super(Comment, cls)._wp_model_factory(blog, mod, manager_db, class_name, extra_attrs=extra_attrs)
        for post_type, post_class in base_post._wp_post_types.items():
            if not post_class._wp_post_type_attrs.get('public'):
                continue
            post_class.comment_set = property(lambda s: base_comment.objects.filter(post__id=s.id))
        return base_comment


class CommentMeta(WPModelMixin, models.Model):
    id = models.BigIntegerField(primary_key=True, db_column='meta_id')
    comment = models.ForeignKey('Comment')
    name = models.CharField(max_length=765, blank=True, db_column='meta_key')
    value = models.TextField(blank=True, db_column='meta_value')
    
    class Meta:
        db_table = u'commentmeta'
        managed = False
        abstract = True

    _wp_model_scope = dict(blog=11)


__blog_models__ = [
    m[1] for m in sorted(
        (v._wp_model_scope['blog'], v) for v in locals().values() if isinstance(v, type) and WPModelMixin in v.__bases__ and 'blog' in getattr(v, '_wp_model_scope', dict())
    )
]
__site_models__ = [
    m[1] for m in sorted(
        (v._wp_model_scope['site'], v) for v in locals().values() if isinstance(v, type) and WPModelMixin in v.__bases__ and 'site' in getattr(v, '_wp_model_scope', dict())
    )
]
