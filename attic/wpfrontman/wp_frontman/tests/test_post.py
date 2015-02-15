import re
import unittest

from django.conf import settings
from django.db import connection
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import set_urlconf, get_resolver
from django.test.client import Client

from wp_frontman.blog import Blog
from wp_frontman.models import Post


class PostTestCase(unittest.TestCase):
    
    def setUp(self):
        self.root_urlconf = settings.ROOT_URLCONF
        settings.ROOT_URLCONF = Blog.get_active().urlconf
        self.cursor = connection.cursor()
        
    def tearDown(self):
        settings.ROOT_URLCONF = self.root_urlconf
        
    def testManager(self):
        db_table = Post._meta.db_table
        # test that the forced filter and published methods actually do what they are supposed to
        self.cursor.execute("select count(*) from %s where post_type='post'" % db_table)
        self.assertEqual(Post.objects.count(), self.cursor.fetchone()[0])
        self.cursor.execute("select count(*) from %s where post_type='post' and post_status='publish'" % db_table)
        self.assertEqual(Post.objects.published().count(), self.cursor.fetchone()[0])
        # test that default ordering is correct, and that published() is accessible from all kinds of querysets
        self.cursor.execute("select ID from %s where post_type='post' order by post_date desc limit 2" % db_table)
        self.assertEqual(repr(Post.objects.values_list('id')[:2]), repr(list(self.cursor.fetchall())))
        self.cursor.execute("select ID from %s where post_type='post' and post_status='publish' order by ID desc limit 2" % db_table)
        result = repr(list(self.cursor.fetchall()))
        self.assertEqual(repr(Post.objects.values_list('id').published()[:2]), result)
        self.assertEqual(repr(Post.objects.published().values_list('id')[:2]), result)
        post = Post.objects.published()[0]
        resolver = get_resolver(Blog.get_active().urlconf)
        kw = resolver.resolve(post.get_absolute_url())[2]
        self.assertEqual(post, Post.objects.get_from_keywords(kw))
        self.assertRaises(ObjectDoesNotExist, Post.objects.get_from_keywords, dict(slug='ksjflkdsjlkj'))
        self.assertRaises(ObjectDoesNotExist, Post.objects.get_from_path, '/a/b/c')
        self.assertEqual(post, Post.objects.get_from_path(post.get_absolute_url()))
        
    def testDbTable(self):
        db_table1 = Post._meta.db_table
        self.cursor.execute("select count(*) from %s where post_type='post'" % db_table1)
        num1 = self.cursor.fetchone()[0]
        blog = Blog.factory(2)
        db_table2 = Post._meta.db_table
        self.assertNotEqual(db_table1, db_table2)
        self.cursor.execute("select count(*) from %s where post_type='post'" % db_table2)
        num2 = self.cursor.fetchone()[0]
        self.assertNotEqual(num1, num2)
        self.assertEqual(Post.objects.count(), num2)
        Blog.default_active()
        
    def testPermalink(self):
        p = Post.objects.get(id=25)
        self.assertEqual(p.get_absolute_url(), '/second-category/second-category-first-child/25-post-in-second-category-first-child/')
        client = Client(HTTP_HOST='ludolo.it')
        response = client.get(p.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(re.findall(r'(?smi)<title>([^<]+)</title>', response.content), ['Post in second category first child | WP Frontman'])
