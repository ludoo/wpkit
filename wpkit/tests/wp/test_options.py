from django.db import connections
from django.test import TestCase
from django_nose.tools import *

from wpkit.wp.options import WPBlogOptions, WPSiteOptions


class OptionsTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        connection = connections['test']
        cursor = connection.cursor()
        cursor.execute("select blog_id from wp_blogs")
        opts = {}
        for row in cursor.fetchall():
            blog_id = row[0]
            if blog_id == 1:
                q = "select * from wp_options"
            else:
                q = "select * from wp_%s_options" % blog_id
            cursor.execute(q)
            opts[blog_id] = WPBlogOptions(cursor.fetchall())
        cls.blog_opts = opts
        cursor.execute("select * from wp_sitemeta where site_id=1")
        cls.site_opts = WPSiteOptions(cursor.fetchall())

    def test_opts(self):
        for blog_id, opts in self.blog_opts.items():
            assert_equals(type(opts._options_data), dict)
        assert_equals(type(self.site_opts._options_data), dict)
        
    def test_len(self):
        assert_equals(len(self.site_opts), len(self.site_opts._options_data))

    def test_contains(self):
        assert_true('admin_user_id' in self.site_opts)
        assert_false('xxx_yyy_spritz' in self.site_opts)
        
    def test_iter(self):
        options = list(self.site_opts)
        assert_equals(len(options), len(self.site_opts))
        assert_true(('admin_user_id', 1) in options)
    
    def test_missing(self):
        assert_true(self.blog_opts[1].dummy_spritz_option is None)
        
    def test_str(self):
        assert_true('home' not in self.blog_opts[1].__dict__)
        assert_equals(self.blog_opts[1].home, 'http://spritz.localtest.me')
        assert_equals(self.blog_opts[1].__dict__['home'], self.blog_opts[1].home)
        
    def test_int(self):
        assert_true(type(self.blog_opts[1].posts_per_page), int)

    def test_int(self):
        assert_equals(self.blog_opts[1].posts_per_page, 3)

    def test_strtobool(self):
        assert_equals(self.blog_opts[1].require_name_email, True)
        
    def test_lambda(self):
        assert_equals(type(self.site_opts.registration), bool)

    def test_unserialize(self):
        rewrite_rules = self.blog_opts[1].rewrite_rules
        assert_equals(type(rewrite_rules), dict)
        assert_true(len(rewrite_rules))

    def test_blog_siteurl(self):
        assert_equals(self.blog_opts[1]._options_data['siteurl'], 'http://spritz.localtest.me')
        assert_equals(self.blog_opts[1].siteurl, 'http://spritz.localtest.me/')
