from django.conf import settings
from django.test import TestCase
from django_nose.tools import *

from wpkit.models import Site, SiteMeta, WPSiteOptions, Blog
#wp.site import SiteError, Site, SiteOptions, Blog


class TestSite(TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.site = Site.objects.get_default()
        #cls.path_site = Site(subdomain_install=False)

    def test_manager_default(self):
        assert_equals(id(self.site), id(Site.objects.get_default()))
        
    def test_fields(self):
        assert_equals(self.site.id, 1)
        assert_equals(self.site.domain, 'spritz.localtest.me')
        assert_equals(self.site.path, '/')
        
    def test_repr(self):
        assert_equals(repr(self.site), '<Site object id 1 wp prefix wp_>')
        
    def test_eq(self):
        assert_equals(Site(id=1), Site(id=1))
        
    def test_hash(self):
        assert_equals(hash(Site(id=1)), hash(Site(id=1)))

    def test_meta(self):
        meta = self.site.meta
        assert_equals(type(meta), WPSiteOptions)
        assert_equals(meta.admin_user_id, 1)
        assert_equals(id(meta), id(self.site.meta))

    def test_blogs(self):
        blogs = self.site.blogs
        assert_true(all(isinstance(b, Blog) for b in blogs))
        assert_equals(len(blogs), 3)
        assert_true(id(blogs) != id(self.site.blogs))

    def test_get_blog(self):
        blog = self.site.get_blog(1)
        assert_equals(type(blog), Blog)
        assert_equals(blog.id, 1)
        assert_equals(id(blog), id(self.site.get_blog(1)))
        
