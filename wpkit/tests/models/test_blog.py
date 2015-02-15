import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django_nose.tools import *

from wpkit.models import Site, Blog, BlogOption, WPBlogOptions, DomainMapping, DB_PREFIX


class TestBlog(TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.site = Site.objects.get_default()
        cls.blogs = cls.site.blogs
        cls.blog = cls.blogs[0]

    def test_site_single(self):
        assert_true(all(id(b.site) == id(self.site) for b in self.blogs))
        
    def test_fields(self):
        assert_equals(
            [(b.id, b.site_id, b.domain, b.path) for b in self.blogs],
            [
                (1, 1, u'spritz.localtest.me', u'/'),
                (2, 1, u'a.spritz.localtest.me', u'/'),
                (3, 1, u'b.spritz.localtest.me', u'/')
            ]
        )

    def test_repr(self):
        assert_equals(repr(self.blog), '<Blog object id 1 site id 1 wp prefix wp_>')

    def test_eq(self):
        assert_equals(self.blog, Blog(id=1, site_id=1))
        
    def test_hash(self):
        assert_equals(hash(self.blog), hash(Blog(id=1, site_id=1)))
        assert_equals(len(set(self.blogs)), 3)
        
    def test_db_prefix(self):
        assert_equals(Blog(1).db_prefix, DB_PREFIX)
        assert_equals(Blog(2).db_prefix, DB_PREFIX+'2_')

    def test_options(self):
        options = self.blog.options
        assert_equals(type(options), WPBlogOptions)
        assert_equals(options.home, 'http://spritz.localtest.me')
        assert_equals(id(options), id(self.blog.options))

    def test_primary_domain(self):
        assert_equals(
            [(b.domain, b.primary_domain) for b in self.blogs],
            [
                (u'spritz.localtest.me', u'spritz.localtest.me'),
                (u'a.spritz.localtest.me', u'a.spritz.localtest.me'),
                (u'b.spritz.localtest.me', u'spritz-b.localtest.me')
            ]
        )
        assert_true(all(
            (id(b.primary_domain) == id(Blog(site_id=1, id=b.id).primary_domain)) for b in self.blogs
        ))

    def test_home(self):
        assert_equals(
            [(b.id, b.home) for b in self.blogs],
            [
                (1L, u'http://spritz.localtest.me'),
                (2L, u'http://a.spritz.localtest.me'),
                (3L, u'http://spritz-b.localtest.me')
            ]
        )
        assert_true(all(
            b.primary_domain in b.home for b in self.blogs
        ))

    def test_settings(self):
        blogs_conf = getattr(settings, 'WPKIT_BLOGS', None)
        settings.WPKIT_BLOGS = None
        if hasattr(self.blog, '_settings'):
            delattr(self.blog, '_settings')
        assert_raises_regexp(
            ImproperlyConfigured,
            '^If settings.WPKIT_BLOGS is set, it must be a dictionary$',
            getattr, self.blog, 'settings'
        )
        settings.WPKIT_BLOGS = {}
        assert_equals(self.blog.settings.keys(), ['date_format'])
        del self.blog.__dict__['settings']
        settings.WPKIT_BLOGS = {(1, 1): 1}
        assert_raises_regexp(
            ImproperlyConfigured,
            '^Settings for blog 1 must be a dictionary$',
            getattr, self.blog, 'settings'
        )
        settings.WPKIT_BLOGS = {(1, 1): {'test':0}}
        assert_equals(self.blog.settings['test'], 0)
        if 'settings' in self.blog.__dict__:
            del self.blog.__dict__['settings']
        if blogs_conf is None:
            delattr(settings, 'WPKIT_BLOGS')
        else:
            settings.WPKIT_BLOGS = blogs_conf
        
    def test_urlconf(self):
        urlconfs = [b.urlconf for b in self.blogs]
        assert_equals(
            [(self.blogs[i].id, u.__name__) for i, u in enumerate(urlconfs)],
            [
                (1, 'wpkit.site_1_blog_1.urls'),
                (2, 'wpkit.site_1_blog_2.urls'),
                (3, 'wpkit.site_1_blog_3.urls')
            ]
        )
        assert_true(all(
            id(u) == id(self.blogs[i].urlconf) for i, u in enumerate(urlconfs)
        ))
        assert_true(all(
            isinstance(u.urlpatterns, list) for u in urlconfs
        ))
        assert_equals(
            [u for u in urlconfs[0].urlpatterns if u.name == 'wpkit_post'][0].regex.pattern,
            u'^(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})/(?P<slug>[^/]+)/$'
        )
        
    def test_models(self):
        assert_equals(
            [(b.id, b.models.__name__) for b in self.blogs],
            [
                (1, 'wpkit.site_1_blog_1.models'),
                (2, 'wpkit.site_1_blog_2.models'),
                (3, 'wpkit.site_1_blog_3.models')
            ]
        )
        assert_true(all(
            b.models.BlogOption._meta.db_table.startswith(b.db_prefix) for b in self.blogs
        ))
        assert_true(all(
            'wpkit.site_%s_blog_%s.models' % (b.site_id, b.id) in sys.modules for b in self.blogs
        ))
