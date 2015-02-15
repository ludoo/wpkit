from django.conf import settings
from django.test import TestCase
from django_nose.tools import *
from django.http.request import HttpRequest
from django.http import HttpResponseRedirect, Http404

from wpkit.middleware import WpKitBlogRoutingMiddleware
from wpkit.models import Site, Blog


class TestBlogRouting(TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.debug_blog_id = getattr(settings, 'WPKIT_DEBUG_BLOG_ID', None)
        settings.WPKIT_DEBUG_BLOG_ID = None
        cls.middleware = WpKitBlogRoutingMiddleware()
        cls.site = Site()
        
    @classmethod
    def tearDownClass(cls):
        if cls.debug_blog_id:
            settings.WPKIT_DEBUG_BLOG_ID = cls.debug_blog_id

    def test_404(self):
        request = HttpRequest()
        request.META['HTTP_HOST'] = 'dummy'
        assert_raises_regexp(
            Http404, r'^No such blog$',
            self.middleware.process_request, request
        )
        
    def test_redirect(self):
        request = HttpRequest()
        request.META['HTTP_HOST'] = 'dummy.localtest.me'
        response = self.middleware.process_request(request)
        assert_equals(type(response), HttpResponseRedirect)
        
    def test_domain(self):
        request = HttpRequest()
        request.META['HTTP_HOST'] = 'spritz-b.localtest.me'
        response = self.middleware.process_request(request)
        assert_equals(type(request.blog), Blog)
        assert_equals(request.blog.id, 3)
