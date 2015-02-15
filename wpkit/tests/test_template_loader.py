from django.apps import apps
from django.conf import settings
from django.template.loaders.filesystem import Loader as FileSystemLoader
from django.test import TestCase
from django_nose.tools import *

from wpkit.template_loader import Loader
from wpkit.models import Site, Blog


class TestTemplateLoader(TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.app = apps.get_app_config('wpkit')
        cls.site = Site.objects.get_default()
        cls.blog = cls.site.get_blog(1)
        cls.loader = Loader()
        
    def test_no_blog(self):
        self.app.blog = None
        assert_equals(
            list(self.loader.get_template_sources('dummy.html')),
            list(FileSystemLoader().get_template_sources('dummy.html'))
        )
        assert_equals(
            list(self.loader.get_template_sources('dummy.html', ('a', 'b'))),
            list(FileSystemLoader().get_template_sources('dummy.html', ('a', 'b')))
        )
        
    def test_blog_no_custom_dir(self):
        self.app.blog = self.blog
        if 'template_dir' in self.blog.settings:
            del self.blog.settings['template_dir']
        assert_equals(
            list(self.loader.get_template_sources('dummy.html')),
            list(FileSystemLoader().get_template_sources('dummy.html'))
        )
        assert_equals(
            list(self.loader.get_template_sources('dummy.html', ('a', 'b'))),
            list(FileSystemLoader().get_template_sources('dummy.html', ('a', 'b')))
        )
        self.blog.settings_reset()
        self.app.blog = None
        
    def test_blog_custom_dir(self):
        self.app.blog = self.blog
        self.blog.settings['template_dir'] = '/c'
        result = list(self.loader.get_template_sources('dummy.html'))
        stock_result = list(FileSystemLoader().get_template_sources('dummy.html'))
        assert_true(len(result) == len(stock_result)+1)
        assert_equals(result[0], '/c/dummy.html')
        result = list(self.loader.get_template_sources('dummy.html', ('a', 'b')))
        stock_result = list(FileSystemLoader().get_template_sources('dummy.html', ('a', 'b')))
        assert_true(len(result) == len(stock_result)+1)
        assert_equals(result[0], '/c/dummy.html')
        self.blog.settings_reset()
        self.app.blog = None
        