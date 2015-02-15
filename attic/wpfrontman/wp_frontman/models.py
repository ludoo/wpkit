# encoding: utf8

import re
import time
import datetime
import hmac
import string
import random
import math

from hashlib import md5
from urllib import quote, unquote
from urlparse import urljoin, urlsplit
from threading import local

from django.conf import settings
from django.db import models, connection, transaction
from django.core.exceptions import ObjectDoesNotExist
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe

from wp_frontman.blog import Blog, php_unserialize, DB_PREFIX
from wp_frontman.managers import *
from wp_frontman.cache import get_key
from wp_frontman.lib.utils import get_date_range, make_tree
from wp_frontman.lib.wp_tagsoup import convert as convert_wp_tagsoup
from wp_frontman.lib.wp_password_hasher import check_password, hash_password
from wp_frontman.lib.htmlstripper import strip_html


WPF_CATEGORIES_AS_SETS = Blog.site.categories_as_sets


# TODO: questo modulo definisce i modelli, e può essere utilizzato direttamente
#       per la versione monoblog; per la versione multiblog va utilizzato
#       come blog.models, ad esempio blog.models.Post, è un descriptor
#       il cui motodo __get__ controlla l'id del blog usato, se trova nella propria cache
#       (id del blog, nome modello) come chiave ne restituisce il valore,
#       crea dinamicamente i modelli e le loro relazioni per il blog e li salva
#       nella propria cache, il blog 1 usa sempre i modelli definiti in questo modulo
#       senza modifiche


class UserSignup(models.Model):
    domain = models.CharField(max_length=600, blank=True, default='', db_index=True)
    path = models.CharField(max_length=300, blank=True, default='')
    title = models.TextField(blank=True, default='')
    login = models.CharField(max_length=180, db_column='user_login', primary_key=True)
    email = models.EmailField(max_length=300, db_column='user_email')
    registered = models.DateTimeField(blank=True, default=datetime.datetime.now)
    activated = models.DateTimeField(blank=True, default=datetime.datetime(year=1, month=1, day=1, hour=0, minute=0, second=0))
    active = models.BooleanField(blank=True, default=False)
    activation_key = models.CharField(max_length=150, db_index=True)
    meta = models.TextField(blank=True, default='a:0:{}')

    class Meta:
        db_table = u'%ssignups' % DB_PREFIX
        managed = False
        
    def activate(self):
        user = User(
            login=self.login, email=self.email, nicename=self.login,
            activation_key=self.activation_key, status=0, display_name=self.login
        )
        # TODO: trap db errors, mark as done instead of saving, log activation, etc.
        user.save()
        self.delete()
        return user

    
class UserManager(models.Manager):
    
    def users_can(self, capability):
        roles = Blog.get_active().capabilities.get(capability)
        if roles is None:
            raise ValueError("Unknown capability")
        users = list()
        for um in UserMeta.objects.filter(name='wp_capabilities').select_related('user'):
            for role, active in php_unserialize(um.value).items():
                if active and role in roles:
                    users.append(um.user)
        return users
        

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
    
    objects = UserManager()
    
    class Meta:
        db_table = u'%susers' % DB_PREFIX
        managed = False

    def __init__(self, *args, **kw):
        super(User, self).__init__(*args, **kw)
        self._usermeta = None
    
    def save(self, *args, **kw):
        if not self.id and not self.passwd:
            self.raw_passwd = ''.join(random.Random().sample(string.letters+string.digits, 8))
            self.passwd = hash_password(self.raw_passwd)
        super(User, self).save(*args, **kw)
        
    def __unicode__(self):
        return u"%s id %s status %s" % (self.login, self.id, self.status)
    
    def get_absolute_url(self):
        return reverse('wpf_author', kwargs=dict(slug=self.nicename or self.login))
    
    def __setstate__(self, d):
        self.__dict__ = d
        self._usermeta = None
    
    def __getattr__(self, attr):
        if self._usermeta is None:
            self._usermeta = dict((m.name, m.value) for m in self.usermeta_set.all())
        if not attr in self._usermeta:
            raise AttributeError("'User' object has no attribute '%s'" % attr)
        return self._usermeta[attr]
    
    def check_password(self, passwd):
        if len(self.passwd) <= 32:
            return md5(passwd).hexdigest() == self.passwd
        return check_password(passwd, self.passwd)
    
    @classmethod
    def user_from_login(cls, login, passwd):
        try:
            user = User.objects.get(login=login)
        except ObjectDoesNotExist:
            return
        if user.check_password(passwd):
            return user
        return
    
    @classmethod
    def login_from_cookie(cls, request, t=None):
        cookie_name = 'wordpress_logged_in_%s' % Blog.site.siteurl_hash
        if not cookie_name in request.COOKIES:
            return
        cookie = request.COOKIES[cookie_name]
        try:
            user_login, expiration, _hmac = unquote(request.COOKIES[cookie_name]).split('|')
            expiration = int(expiration)
        except (TypeError, ValueError):
            return
        if expiration < (t or time.time()):
            return
        return user_login, expiration, _hmac
    
    @classmethod
    def user_from_cookie(cls, request, user_login=None, expiration=None, _hmac=None):
        # >>> unquote(cookies['wordpress_logged_in_9598d7ae41530e836fb82befde1d1df6'])
        # ['ludo', '1302504664', '358f728c39b2b591e5627594d393174a']
        if not all((user_login, expiration, _hmac)):
            try:
                user_login, expiration, _hmac = cls.login_from_cookie(request)
            except (TypeError, ValueError):
                return
        try:
            user = User.objects.get(login=user_login)
        except ObjectDoesNotExist:
            return
        key = Blog.site.wp_hash(
            "%s%s|%s" % (user.login, user.passwd[8:12], expiration),
            'logged_in'
        )
        hash = hmac.new(key, "%s|%s" % (user.login, expiration)).hexdigest()
        if _hmac != hash:
            return
        request.wp_user = user
        return user
    
    @classmethod
    def verify_nonce(cls, request, nonce, action=-1, t=None):
        user = request.wp_user or cls.user_from_cookie(request)
        if not user:
            return
        t = int(math.ceil((t or time.time()) / (86400/2.0)))
        for i in (0, 1):
            n = "%s%s%s" % (t-i, action, user.id)
            if Blog.site.wp_hash(n, 'nonce')[-12:-2] == nonce:
                return i+1
    
    def get_logged_in_cookie(self):
        expiration = int(time.time()) + 60*60*24*30
        key = Blog.site.wp_hash(
            "%s%s|%s" % (self.login, self.passwd[8:12], expiration),
            'logged_in'
        )
        hash = hmac.new(key, "%s|%s" % (self.login, expiration)).hexdigest()
        return dict(
            key='wordpress_logged_in_%s' % Blog.site.siteurl_hash,
            max_age=expiration,
            expires=time.strftime("%a, %d %b %Y %H:00:00 GMT", time.gmtime(expiration)),
            value=quote("%s|%s|%s" % (self.login.encode('utf-8'), expiration, hash))
        )
    

class UserMeta(models.Model):
    user = models.ForeignKey(User)
    id = models.BigIntegerField(primary_key=True, db_column='umeta_id')
    name = models.CharField(max_length=765, blank=True, db_column='meta_key')
    value = models.TextField(blank=True, db_column='meta_value')
    
    class Meta:
        db_table = u'%susermeta' % DB_PREFIX
        managed = False

        
class BasePost(models.Model):
    
    _permalink_tokens = tuple(Blog.wp_permalink_map.get(k, k) for k in Blog.wp_permalink_tokens)
    _permalink_tokens_request_map = dict(author='author__nicename', category='postcategories__category__term__slug', tag='posttags__tag__term__slug')
    _date_tokens = ('year', 'month', 'day', 'hour', 'minute', 'second')
    _more_re = re.compile(r'(?smu)<!--more[^>]?-->')
    _end_tags_re = re.compile(r'(?su)(\s*(?:\s*</(?:p|div)>\s*)*\s*)$')
    _excerpt_stripper_re = re.compile(r'(?smu)</?[^>]+>')
    _space_splitter_re = re.compile(r'(?smu)\s+')
    
    id = models.BigIntegerField(primary_key=True, db_column='ID')
    author = models.ForeignKey(User, db_column='post_author')
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
    parent = models.ForeignKey('BasePost', blank=True, db_column='post_parent', null=True, default=0)
    guid = models.CharField(max_length=765)
    menu_order = models.IntegerField()
    post_type = models.CharField(max_length=60)
    mime_type = models.CharField(max_length=300, db_column='post_mime_type')
    comment_count = models.BigIntegerField()
    
    base_taxonomy = models.ManyToManyField('TaxonomyTerm', through='PostTerms')
    #tags = models.ManyToManyField('PostTag', through='PostTags')
    
    objects = BasePostManager()
    
    class Meta:
        db_table = u'%sposts'
        db_table_arg = Blog.get_active_db_prefix
        ordering = ('-date',)
        managed = False
    
    def __init__(self, *args, **kw):
        super(BasePost, self).__init__(*args, **kw)
        self._reset_cache()
        
    def save(self, *args, **kw):
        super(BasePost, self).save(*args, **kw)
        self._reset_cache()

    def __unicode__(self):
        return u"%s id %s status %s" % (self.post_type, self.id, self.status)
    
    @property
    def permalink_tokens(self):
        if self.post_type != 'post':
            return dict()
        blog_tokens = Blog.get_active().permalink_tokens
        tokens = dict()
        for k in self._permalink_tokens:
            if not k in blog_tokens:
                continue
            v = getattr(self, k)
            tokens[k] = v if not hasattr(v, 'permalink_token') else v.permalink_token
        return tokens
    
    def get_absolute_url(self):
        if not 'absolute_url' in self._cache:
            if self.post_type == 'page':
                url = reverse('wpf_index')
                if not url.endswith('/'):
                    url += '/'
                url += self.slug
                if getattr(settings, 'APPEND_SLASH', False):
                    url += '/'
            else:
                url = reverse('wpf_post', kwargs=self.permalink_tokens)
            self._cache['absolute_url'] = url
        return self._cache['absolute_url']
    
    def get_permalink(self):
        return urljoin(Blog.get_active().home, self.get_absolute_url())

    permalink = property(get_permalink) # TODO: check older themes and keep only the property

    def get_trackback_url(self):
        d = dict((k, getattr(self, k)) for k in self._permalink_tokens if k in Blog.get_active().permalink_tokens)
        return reverse('wpf_trackback', kwargs=d)
    
    @classmethod
    def fill_taxonomy_cache(cls, posts, ordering=None):
        if not posts:
            return
        d = dict((p.id, p._cache.setdefault('taxonomy', list())) for p in posts)
        qs = PostTerms.objects.select_related('term_taxonomy', 'term_taxonomy__term', 'term_taxonomy__parent', 'term_taxonomy__parent__term').filter(post__in=d.keys())
        if ordering and type(ordering) in (list, tuple):
            qs = qs.order_by(*ordering)
        for t in qs:
            d[t.post_id].append(t.term_taxonomy)

    @classmethod
    def get_permalink_filters(cls, **tokens):
        dt = dict()
        filters = dict()
        for k, v in tokens.items():
            if not k in cls._permalink_tokens:
                continue
            if k in cls._date_tokens:
                dt[k] = v
            else:
                filters[cls._permalink_tokens_request_map.get(k, k)] = v
        if dt:
            try:
                dt_start, dt_end = get_date_range(limit_to_days=True, **dt)
            except (TypeError, ValueError):
                pass
            else:
                if dt_start == dt_end:
                    filters['date'] = dt_start
                else:
                    filters['date__range'] = (dt_start, dt_end)
        return filters
    
    @property
    def taxonomy(self):
        if not 'taxonomy' in self._cache:
            self._cache['taxonomy'] = self.base_taxonomy.select_related('term', 'parent', 'parent__term')
        return self._cache['taxonomy']
    
    @property
    def categories(self):
        return  list(set(t for t in self.taxonomy if t.taxonomy == 'category'))
    
    @property
    def category(self):
        if not self.categories:
            return
        if Blog.site.support_category_order:
            # sort categories giving precedence to their level, then their order
            return sorted([(0 if not c.parent_id else c.parent.term.order, c.term.order, c.term.slug, c) for c in self.categories])[0][3]
        return self.categories[0]
        
    @property
    def tags(self):
        return  [t for t in self.taxonomy if t.taxonomy == 'post_tag']
    
    @property
    def comments(self):
        if not 'comments' in self._cache:
            self._cache['comments'] = self.basecomment_set.approved()
        return [c for c in self._cache['comments'] if c.comment_type == '']
    
    @property
    def post_format(self):
        formats = [t for t in self.taxonomy if t.taxonomy == 'post_format']
        if not formats:
            return ''
        return formats[0]
    
    @property
    def trackbacks(self):
        if not 'comments' in self._cache:
            self._cache['comments'] = self.basecomment_set.approved()
        return [c for c in self._cache['comments'] if c.comment_type in ('trackback', 'pingback')]
    
    # map wordpress permalink tokens to properties
    
    year = property(lambda s: s.date.year)
    month = property(lambda s: "%02d" % s.date.month)
    day = property(lambda s: "%02d" % s.date.day)
    hour = property(lambda s: "%02d" % s.date.hour)
    minute = property(lambda s: "%02d" % s.date.minute)
    second = property(lambda s: "%02d" % s.date.second)
    
    # TODO: add missing tokens
    
    timestamp = property(lambda s: int(time.mktime(s.date.timetuple())))
    
    def _reset_cache(self):
        self._cache = dict()
        
    # alias here so that we can use it in feed templates
    use_excerpts_in_feeds = getattr(Blog.get_active(), 'rss_use_excerpt', False)

    @property
    def meta_description(self):
        if not self.content:
            return ''
        return self._excerpt_stripper_re.sub('', self.content)[:155]
        
    @property
    def excerpt(self):
        if self._excerpt:
            return self._excerpt
        # TODO: pay more attention to entities, comments, etc.
        if not self.content:
            return ''
        tokens = self._space_splitter_re.split(self._excerpt_stripper_re.sub('', self.content))
        if len(tokens) > 45:
            tokens = tokens[:45]
        return u' '.join(tokens).replace("\n\n", "</p>\n<p>")
        
    @property
    def content_stripped(self):
        return strip_html(self.content)
    
    @property
    def more(self):
        if not 'has_more' in self._cache:
            self._bootstrap_content()
        return self._cache['has_more']
    
    @property
    def summary(self):
        if not 'summary' in self._cache:
            self._bootstrap_content()
        return self._cache['summary']
    
    @property
    def content_parsed(self):
        if not 'content_parsed' in self._cache:
            self._bootstrap_content()
        return mark_safe(self._cache['content_parsed'])
        
    @property
    def summary_parsed(self):
        if not 'summary_parsed' in self._cache:
            self._bootstrap_content()
        return mark_safe(self._cache['summary_parsed'])
    
    @property
    def summary_parsed_more(self):
        return self.add_more(self.summary_parsed)
    
    def add_more(self, summary, text=None, pre=None, post=None):
        # don't cache as it will be typically used once for each post
        more_link = u'%s<a href="%s#more-%s">%s</a>%s' % (
            pre or u"&hellip;",
            self.get_absolute_url(),
            self.id,
            text or u"Read the rest of this entry &raquo;",
            post or u''
        )
        return self._end_tags_re.sub(ur"%s\1" % more_link, summary)
    
    def _parse_content_filtered(self):
        """Return a tuple with preformatted parsed summary (the content up
           to the more tag) and content (all content including the more tag) if
           they exist. Return None otherwise.
        """
        if not self.content_filtered:
            return
        try:
            summary, content, tstamp = self.content_filtered.split(chr(0))
        except (TypeError, ValueError):
            return
        try:
            tstamp = int(tstamp)
        except (TypeError, ValueError):
            return
        if int(time.mktime(self.modified_gmt.timetuple())) == tstamp:
            # we can use the filtered content
            return summary, content
        
    def _parse_content(self):
        content = self.content
        if not(content.strip()):
            return '', ''
        m = self._more_re.search(content)
        if m:
            summary = content[:m.start()]
        else:
            summary = ''
        return summary, content
    
    def _bootstrap_content(self):
        summary, content = self._parse_content()
        try:
            summary_parsed, content_parsed = self._parse_content_filtered()
        except TypeError:
            summary_parsed = '' if not summary else convert_wp_tagsoup(summary)
            content_parsed = convert_wp_tagsoup(content)
        has_more = bool(summary)
        # easy: add the #more anchor to the full content
        content_parsed = self._more_re.sub('<span id="more-%s"></span>' % self.id, content_parsed)
        self._cache['summary'] = summary or content
        self._cache['summary_parsed'] = summary_parsed or content_parsed
        self._cache['content_parsed'] = content_parsed
        self._cache['has_more'] = has_more

    @property
    def featured_image(self):
        if not 'featured_image' in self._cache:
            self._bootstrap_attachments([self])
        return self._cache['featured_image']
    
    @property
    def thumbnail(self):
        featured_image = self.featured_image or dict()
        return featured_image.get('sizes', dict()).get('thumbnail')
    
    @property
    def attachments(self):
        if not 'attachments' in self._cache:
            self._bootstrap_attachments([self])
        return self._cache['attachments']
        
    @classmethod
    def _bootstrap_attachments(cls, posts):
        if posts is None:
            return posts
        if not posts:
            for p in posts:
                p._cache['attachments'] = p._cache['attached_files'] = p._cache['featured_image'] = None
            return
        post_ids = ', '.join(str(p.id) for p in posts)
        cursor = connection.cursor()
        res = cursor.execute("""
            select p.post_parent as parent_id, pm.post_ID as post_id, pm.meta_key, pm.meta_value
            from %s pm
            inner join %s p on p.ID=pm.post_ID
            where
                (pm.post_id in (%s) and pm.meta_key='_thumbnail_id') or
                (pm.post_id in (select meta_value from %s where post_id in (%s) and meta_key='_thumbnail_id') and meta_key in ('_wp_attachment_metadata', '_wp_attachment_image_alt')) or
                (p.post_parent in (%s) and pm.meta_key in ('_wp_attachment_metadata', '_wp_attachment_image_alt'))
        """ % (PostMeta._meta.db_table, cls._meta.db_table, post_ids, PostMeta._meta.db_table, post_ids, post_ids))
        if not res:
            for p in posts:
                p._cache['attachments'] = p._cache['attached_files'] = p._cache['featured_image'] = None
            return
        # attached files can be more than one per post
        # attachments can be more than one per post
        # featured image is a single one per post
        attachments = dict()        # attachment post id / attachment data
        attachment_alt = dict()     # attachment post id / alt text
        post_attachments = dict()   # post id / list of attachment post ids
        featured_images = dict()    # post id / attachment post id
        fileupload_path = Blog.get_active().fileupload_path.split('/')
        for post_id, attachment_id, key, value in cursor.fetchall():
            if key == '_thumbnail_id':
                try:
                    featured_images[attachment_id] = int(value) # post_id attachment_id
                except (TypeError, ValueError):
                    pass
                continue
            if key == '_wp_attachment_image_alt':
                attachment_alt[attachment_id] = value
            if key == '_wp_attachment_metadata':
                try:
                    data = php_unserialize(value.encode('utf-8'))
                except ValueError:
                    continue
                image_file, image_sizes = data.get('file'), data.get('sizes', dict())
                if image_file:
                    # add the path from the image file to the other sizes
                    path = fileupload_path + urlsplit(image_file).path.split('/')
                    data['path'] = '/'.join(path)
                    for k, v in image_sizes.items():
                        if 'file' in v:
                            v['path'] = '/'.join(path[:-1] + [v['file']])
                data['attachment_post_id'] = attachment_id
                # TODO: use a proper class for attachments, with proper permalinks etc
                attachments[attachment_id] = data
                post_attachments.setdefault(post_id, list()).append(attachment_id)
        for attachment_id, alt in attachment_alt.items():
            if not attachment_id in attachments:
                continue
            attachments[attachment_id]['alt_text'] = alt
        for post in posts:
            post._cache['attachments'] = post._cache['featured_image'] = None
            if post.id in post_attachments:
                post._cache['attachments'] = [attachments[i] for i in post_attachments.get(post.id, list())]
            if post.id in featured_images:
                post._cache['featured_image'] = attachments.get(featured_images.get(post.id))
            

class Post(BasePost):
    
    objects = PostManager()
    
    class Meta:
        db_table = u'%sposts'
        db_table_arg = Blog.get_active_db_prefix
        ordering = ('-date',)
        proxy = True
        managed = False
        
    @property
    def next(self):
        if not 'next' in self._cache:
            self._cache['next'] = self.get_next_by_date(status='publish')
        return self._cache['next']
    
    @property
    def previous(self):
        if not 'previous' in self._cache:
            self._cache['previous'] = self.get_previous_by_date(status='publish')
        return self._cache['previous']
    
    def set_to_revision(self, revision_id):
        try:
            revision = BasePost.objects.get(id=revision_id, post_type='revision', parent=self)
        except ObjectDoesNotExist:
            return
        # preview only title and content
        self.title = revision.title
        self.content = revision.content
        self._reset_cache()
        

class PostMeta(models.Model):
    id = models.BigIntegerField(primary_key=True, db_column='meta_id')
    post = models.ForeignKey(BasePost)
    name = models.CharField(max_length=765, db_column='meta_key')
    value = models.TextField(db_column='meta_value')
    
    class Meta:
        db_table = u'%spostmeta'
        db_table_arg = Blog.get_active_db_prefix
        managed = False


class Page(BasePost):
    
    objects = PageManager()
    
    class Meta:
        db_table = u'%sposts'
        db_table_arg = Blog.get_active_db_prefix
        ordering = ('menu_order',)
        proxy = True
        managed = False
        
        
class Term(models.Model):
    id = models.BigIntegerField(primary_key=True, db_column='term_id')
    name = models.CharField(max_length=600)
    slug = models.CharField(unique=True, max_length=255) #, max_length=600)
    group = models.BigIntegerField(db_column='term_group')
    
    if Blog.site.support_category_order:
        # add support for the my category order plugin
        order = models.IntegerField(db_column='term_order', db_index=True)
        supports_my_cat_order = True
    else:
        supports_my_cat_order = False
        
    class Meta:
        db_table = u'%sterms'
        db_table_arg = Blog.get_active_db_prefix
        managed = False
        ordering = ('name',)
        
    def __unicode__(self):
        return u"%s id %s" % (self.slug, self.id)


class TermTaxonomyBase(models.Model):
    
    id = models.IntegerField(primary_key=True, db_column='term_taxonomy_id')
    term = models.ForeignKey(Term, db_column='term_id', unique=True)
    taxonomy = models.CharField(max_length=96, db_index=True)
    description = models.TextField()
    #parent = models.ForeignKey('TermTaxonomy', blank=True, null=True, db_column='parent')
    count = models.BigIntegerField()
    
    class Meta:
        db_table = u'%sterm_taxonomy'
        db_table_arg = Blog.get_active_db_prefix
        managed = False
        unique_together = (('term', 'taxonomy'),)
        ordering = ('term__name',)
        abstract = True
        
    def __unicode__(self):
        return u"%s id %s term id %s parent %s" % (self.taxonomy, self.id, self.term_id, getattr(self, 'parent_id', None))

    # TODO: move the following to mixin classes or something
    
    @property
    def permalink_token(self):
        return self.term.slug

    def get_absolute_url(self):
        # this method is overridden:
        #  - for categories in the Category class (special cased as it's a key object)
        #  - for hierarchical taxonomies in the HierarchicalTaxonomyMixin class
        if not hasattr(self, '_get_absolute_url'):
            #print "url for", 'wpf_%s' % self.taxonomy, "slug", self.term.slug
            self._absolute_url = reverse('wpf_%s' % self.taxonomy, kwargs=dict(slug=self.term.slug))
        return self._absolute_url
    
    @property
    def taxonomy_slug(self):
        """Mainly used by the twentyten template"""
        return self.taxonomy.split('_')[-1]


class TermRelationshipBase(models.Model):
    #post = models.ForeignKey(Post, db_column='object_id')
    #taxonomy = models.ForeignKey(TermTaxonomy, limit_choices_to=dict(taxonomy='category'), db_column='term_taxonomy_id')
    order = models.IntegerField(db_column='term_order')
    
    class Meta:
        db_table = u'%sterm_relationships'
        db_table_arg = Blog.get_active_db_prefix
        ordering = ('order',)
        managed = False
        abstract = True
        
        
class TaxonomyTerm(TermTaxonomyBase):
    
    _cache = local()
    
    parent = models.ForeignKey('TaxonomyTerm', blank=True, null=True, db_column='parent', to_field='term')
    objects = filtered_manager_factory('TaxonomyTermManager', dict(), bases=(TaxonomyManagerMixin, models.Manager))()

    @classmethod
    def get_custom_taxonomy_class(cls, taxonomy, blog=None):
        blog = blog or Blog.get_active()
        taxonomy_attrs = blog.get_taxonomy_attributes(taxonomy)
        if not taxonomy_attrs:
            raise TypeError("No taxonomy '%s' for blog id '%s'" % (taxonomy, blog.blog_id))
        key = '%s_%s' % (taxonomy, blog.blog_id)
        try:
            return getattr(cls._cache, key)
        except AttributeError:
            pass
        if taxonomy_attrs.get('hierarchical'):
            bases = (HierarchicalTaxonomyTermMixin, TermTaxonomyBase)
        else:
            bases = (TermTaxonomyBase,)
        class_suffix = '%s%s' % (taxonomy.title(), blog.blog_id)
        # TODO: create the relationship model with this taxonomy's objects, disablinh the reverse relationship from the object
        new_class = type(
            'TermTaxonomy%s' % class_suffix,
            bases,
            {
                '_taxonomy':key,
                '__module__':__name__,
                'objects':filtered_manager_factory(
                    '%sManager' % class_suffix,
                    dict(taxonomy=taxonomy),
                    bases=(TaxonomyManagerMixin, models.Manager)
                )()
            }
        )
        setattr(cls._cache, key, new_class)
        return new_class

    
##### hairy stuff #####
# partial inspiration from here
# http://stackoverflow.com/questions/2542157/subclassed-django-models-with-integrated-querysets


def __new__taxonomy__(cls, *args, **kw):
    # TODO: use a dict somewhere to map names to classes, so that we can manipulate it for custom taxonomies
    if kw:
        taxonomy = kw.get('taxonomy')
    elif args:
        taxonomy = args[2]
    if taxonomy == 'category':
        _cls = Category
    elif taxonomy == 'post_tag':
        _cls = Tag
    elif taxonomy == 'link_category':
        _cls = LinkCategory
    else:
        # custom taxonomy, check if we have one defined for the active blog
        try:
            _cls = cls.get_custom_taxonomy_class(taxonomy)
        except TypeError:
            _cls = cls
    if not 'parent' in [f.name for f in _cls._meta.fields]:
        if kw:
            if 'parent_id' in kw:
                del kw['parent_id']
        elif len(args) == 6:
            args = args[:3] + args[-1:]
    obj = super(_cls, _cls).__new__(_cls, *args, **kw)
    # uhm...
    obj.__init__(*args, **kw)
    return obj


TaxonomyTerm.__new__ = staticmethod(__new__taxonomy__)
    

class PostTerms(TermRelationshipBase):
    # TODO: find a less hackish way to use this table's compound primary key
    post = models.ForeignKey(BasePost, db_column='object_id', primary_key=True)
    term_taxonomy = models.ForeignKey(TaxonomyTerm, db_column='term_taxonomy_id', primary_key=True)
    
    class Meta(TermRelationshipBase.Meta):
        ordering = ('order', 'term_taxonomy') # 'term_taxonomy__taxonomy', 'term_taxonomy__term__name')


class HierarchicalTaxonomyTermMixin(object):

    def __init__(self, *args, **kw):
        super(HierarchicalTaxonomyTermMixin, self).__init__(*args, **kw)
        if self.parent_id == 0:
            self.parent_id = None
            
    @property
    def permalink_token(self):
        if self.parent_id:
            return self.get_hierarchy_slug() + self.term.slug
        return self.term.slug
            
    @property
    def hierarchy_root(self):
        if not self.parent_id:
            return self
        return self.get_hierarchy()[-1]
    
    def get_hierarchy(self):
        map = dict((obj.term_id, obj) for obj in self.get_all())
        parents = list()
        obj = self
        while True:
            if not obj.parent_id:
                break
            obj = map[obj.parent_id]
            parents.append(obj)
        return parents
    
    def get_hierarchy_slug(self):
        hierarchy = [obj.term.slug for obj in self.get_hierarchy()]
        if not hierarchy:
            return
        return '/'.join(reversed(hierarchy)) + '/'
    
    def get_absolute_url(self):
        if not hasattr(self, '_absolute_url'):
            d = dict(slug=self.term.slug)
            parents = self.get_hierarchy_slug()
            if parents:
                d['parents'] = parents
            self._absolute_url = reverse('wpf_%s' % self.taxonomy, kwargs=d)
        return self._absolute_url

    @classmethod
    def get_all(cls, as_tree=False):
        blog = Blog.get_active()
        taxonomy_key = getattr(cls, '_taxonomy', cls.__name__.lower())
        value = blog.cache.get(taxonomy_key if not as_tree else (taxonomy_key + '_tree'))
        if value:
            return value
        blog_id = blog.blog_id
        keys = (get_key(blog_id, 'taxonomy'), get_key(blog_id, 'models.%s.all' % taxonomy_key))
        values = cache.get_many(keys)
        timestamp = values.get(keys[0])
        value = values.get(keys[1])
        if value:
            t, v = value
            if timestamp and int(timestamp) > int(t):
                value = None
            else:
                value = v
        if not value:
            value = list(cls.objects.select_related('term', 'parent'))
            cache.set(keys[1], (time.time(), value))
        blog.cache[taxonomy_key] = value
        tree_value = make_tree(value)
        blog.cache[taxonomy_key + '_tree'] = tree_value
        return value if not as_tree else tree_value
    

class Category(HierarchicalTaxonomyTermMixin, TermTaxonomyBase):
    
    parent = models.ForeignKey('Category', blank=True, null=True, db_column='parent', to_field='term')
    posts = models.ManyToManyField(Post, through='PostCategories')
    pages = models.ManyToManyField(Page, through='PageCategories')
    objects = filtered_manager_factory('CategoryManager', dict(taxonomy='category'), bases=(TaxonomyManagerMixin, models.Manager))()
    
    @property
    def permalink_token(self):
        if WPF_CATEGORIES_AS_SETS and self.parent_id:
            return self.get_hierarchy_slug() + self.term.slug
        return self.term.slug
    
    def get_absolute_url(self):
        if not hasattr(self, '_absolute_url'):
            d = dict(slug=self.term.slug)
            if WPF_CATEGORIES_AS_SETS and self.parent_id:
                parents = self.get_hierarchy_slug()
                if parents:
                    d['parents'] = parents
            self._absolute_url = reverse('wpf_category', kwargs=d)
        return self._absolute_url
    

class PostCategories(TermRelationshipBase):
    # TODO: find a less hackish way to use this table's compound primary key
    post = models.ForeignKey(Post, db_column='object_id', primary_key=True)
    category = models.ForeignKey(Category, db_column='term_taxonomy_id', primary_key=True)
    objects = filtered_manager_factory('PostCategoriesManager', dict(category__taxonomy='category', post__post_type='post'))()


class PageCategories(TermRelationshipBase):
    # TODO: find a less hackish way to use this table's compound primary key
    page = models.ForeignKey(Page, db_column='object_id', primary_key=True)
    category = models.ForeignKey(Category, db_column='term_taxonomy_id', primary_key=True)
    objects = filtered_manager_factory('PageCategoriesManager', dict(category__taxonomy='category', page__post_type='page'))()


class Tag(TermTaxonomyBase):
    #parent = models.ForeignKey('Tag', blank=True, null=True, db_column='parent')
    posts = models.ManyToManyField(Post, through='PostTags')
    pages = models.ManyToManyField(Page, through='PageTags')
    objects = filtered_manager_factory('TagManager', dict(taxonomy='post_tag'), bases=(TaxonomyManagerMixin, models.Manager))()
    
    class Meta(TermTaxonomyBase.Meta):
        ordering = ('term',)

    def get_absolute_url(self):
        if not hasattr(self, '_absolute_url'):
            self._absolute_url = reverse('wpf_post_tag', kwargs=dict(slug=self.term.slug))
        return self._absolute_url
        
      
class PostTags(TermRelationshipBase):
    # TODO: find a less hackish way to use this table's compound primary key
    post = models.ForeignKey(Post, db_column='object_id', primary_key=True)
    tag = models.ForeignKey(Tag, db_column='term_taxonomy_id', primary_key=True)
    objects = filtered_manager_factory('PostTagsManager', dict(tag__taxonomy='post_tag', post__post_type='post'))()

    class Meta(TermRelationshipBase.Meta):
        ordering = ('tag',)
    

class PageTags(TermRelationshipBase):
    # TODO: find a less hackish way to use this table's compound primary key
    page = models.ForeignKey(Page, db_column='object_id', primary_key=True)
    tag = models.ForeignKey(Tag, db_column='term_taxonomy_id', primary_key=True)
    objects = filtered_manager_factory('PageTagsManager', dict(tag__taxonomy='post_tag', page__post_type='page'))()

    class Meta(TermRelationshipBase.Meta):
        ordering = ('tag',)
    

class LinkCategory(HierarchicalTaxonomyTermMixin, TermTaxonomyBase):

    taxonomy_name = 'link_category'
    
    parent = models.ForeignKey('LinkCategory', blank=True, null=True, db_column='parent', to_field='term')
    links = models.ManyToManyField('Link', through='LinkCategories')
    objects = filtered_manager_factory('LinkCategoryManager', dict(taxonomy='link_category'), bases=(TaxonomyManagerMixin, models.Manager))()


class LinkCategories(TermRelationshipBase):
    
    link = models.ForeignKey('Link', db_column='object_id', primary_key=True)
    category = models.ForeignKey(LinkCategory, db_column='term_taxonomy_id', primary_key=True)
    objects = filtered_manager_factory('LinkCategoriesManager', dict(category__taxonomy='link_category'))()


class Link(models.Model):
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
    categories = models.ManyToManyField('LinkCategory', through='LinkCategories')    
    
    objects = LinkManager()
    
    class Meta:
        db_table = u'%slinks'
        db_table_arg = Blog.get_active_db_prefix


class BaseComment(models.Model):
    id = models.AutoField(primary_key=True, db_column='comment_ID')
    base_post = models.ForeignKey(BasePost, db_column='comment_post_ID')
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
    comment_type = models.CharField(max_length=60)
    parent = models.ForeignKey('BaseComment', blank=True, db_column='comment_parent', null=True, default=0)
    user = models.ForeignKey(User, blank=True, null=True, default=0)
    
    objects = BaseCommentManager()
    
    class Meta:
        db_table = u'%scomments'
        db_table_arg = Blog.get_active_db_prefix
        ordering = ('date', 'id') # if getattr(blog, 'comment_order', None) == 'asc' else ('-date', '-id')
        managed = False
        #abstract = True

    def __unicode__(self):
        return u"%s id %s for post %s" % (self.comment_type or 'comment', self.id, self.base_post_id)
    
    @transaction.commit_on_success
    def save(self, *args, **kw):
        increment_post = not self.id and str(self.approved) == '1'
        # set parent to 0 if we are using the crappy default WP ddl
        if self.parent_id is None: # and 'default' in nullable_fields_kw:
            self.parent_id = 0
        super(BaseComment, self).save(*args, **kw)
        if increment_post:
            cursor = connection.cursor()
            cursor.execute(
                ("update %s set comment_count=comment_count + 1 where ID=%%s" % self.base_post._meta.db_table),
                (self.base_post_id,)
            )
    
    ### don't delete from django unless we have fixed the awful WP ddl, or we'll get an exception on null related objects ###
    #@transaction.commit_on_success
    #def delete(self, *args, **kw):
    #    super(BaseComment, self).delete(*args, **kw)
    #    if str(self.approved) == '1':
    #        cursor = connection.cursor()
    #        cursor.execute(
    #            ("update %s set comment_count=comment_count - 1 where ID=%%s" % self.base_post._meta.db_table),
    #            (self.base_post_id,)
    #        )
        
    @property
    def content(self):
        if not self.rawcontent:
            return ''
        return convert_wp_tagsoup(self.rawcontent)
    
    def get_absolute_url(self):
        if not self.base_post:
            return None
        return self.base_post.get_absolute_url() + '#comment-%s' % self.id
    
    def get_permalink(self):
        if not self.base_post:
            return None
        return self.base_post.get_permalink() + '#comment-%s' % self.id

    @property
    def gravatar_hash(self):
        return md5(self.author_email.strip().lower().encode('utf-8')).hexdigest()
    
    
class Comment(BaseComment):
    objects = filtered_manager_factory('CommentManager', dict(comment_type=''), (BaseCommentManager,))()
    
    class Meta:
        db_table = u'%scomments'
        db_table_arg = Blog.get_active_db_prefix
        proxy = True
    

class Trackback(BaseComment):
    objects = filtered_manager_factory('TrackbackManager', dict(comment_type='trackback'), (BaseCommentManager,))()
    
    class Meta:
        db_table = u'%scomments'
        db_table_arg = Blog.get_active_db_prefix
        proxy = True


class Pingback(BaseComment):
    objects = filtered_manager_factory('PingbackManager', dict(comment_type='pingback'), (BaseCommentManager,))()
    
    class Meta:
        db_table = u'%scomments'
        db_table_arg = Blog.get_active_db_prefix
        proxy = True


class CommentMeta(models.Model):
    id = models.BigIntegerField(primary_key=True, db_column='meta_id')
    comment = models.ForeignKey(BaseComment)
    name = models.CharField(max_length=765, blank=True, db_column='meta_key')
    value = models.TextField(blank=True, db_column='meta_value')
    
    class Meta:
        db_table = u'%scommentmeta'
        db_table_arg = Blog.get_active_db_prefix


# non-orm based models
# TODO: define a fake queryset class so that we can do stuff like
# ArchiveMonth.objects.order_by('count') etc.

class ArchiveYear(object):
    
    def __init__(self, year, id__count):
        self.year = year
        self.count = id__count
        self._dt = None

    @classmethod
    def all(cls, desc=False, orderby_count=False, num=None):
        ordering = ('year',) if not desc else ('-year',)
        if orderby_count:
            ordering = ('-id__count',) + ordering
        qs = Post.objects.published().extra(
            select=dict(year='year(post_date)')
        ).values('year').annotate(models.Count('id')).order_by(*ordering)
        if num is not None:
            qs = qs[:num]
        return [cls(**r) for r in qs]

    @property
    def dt(self):
        if self._dt is None:
            self._dt = datetime.date(year=self.year, month=1, day=1)
        return self._dt
    
    def get_absolute_url(self):
        return  reverse('wpf_archives', kwargs=dict(year=self.year))
    

class ArchiveMonth(object):
    
    def __init__(self, year, month, id__count):
        self.year = year
        self.month = month
        self.count = id__count
        self._dt = None

    @classmethod
    def all(cls, desc=False, orderby_count=False, num=None):
        ordering = ('year', 'month') if not desc else ('-year', '-month')
        if orderby_count:
            ordering = ('-id__count',) + ordering
        qs = Post.objects.published().extra(
            select=dict(year='year(post_date)', month='month(post_date)')
        ).values('year', 'month').annotate(models.Count('id')).order_by(*ordering)
        if num is not None:
            qs = qs[:num]
        return [cls(**r) for r in qs]

    @property
    def year_month(self):
        return self.dt.strftime("%Y%m")
    
    @property
    def dt(self):
        if self._dt is None:
            self._dt = datetime.date(year=self.year, month=self.month, day=1)
        return self._dt
    
    def get_absolute_url(self):
        return  reverse('wpf_archives', kwargs=dict(year=self.year, month=self.month))
    

# register actions for the relevant signals
from wp_frontman.actions import register_actions
register_actions()


# declare the model we use for background jobs
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
        
