import unittest

from django.conf import settings
from django.db import connection

from wp_frontman.blog import Blog
from wp_frontman.models import BasePost


class BasePostTestCase(unittest.TestCase):
    
    def setUp(self):
        self.root_urlconf = settings.ROOT_URLCONF
        settings.ROOT_URLCONF = Blog.get_active().urlconf
        self.cursor = connection.cursor()
        
    def tearDown(self):
        settings.ROOT_URLCONF = self.root_urlconf
        
    def testManager(self):
        db_table = BasePost._meta.db_table
        # test that the forced filter and published methods actually do what they are supposed to
        self.cursor.execute("select count(*) from %s" % db_table)
        self.assertEqual(BasePost.objects.count(), self.cursor.fetchone()[0])
        self.cursor.execute("select count(*) from %s where post_status='publish'" % db_table)
        self.assertEqual(BasePost.objects.published().count(), self.cursor.fetchone()[0])
        # test that default ordering is correct, and that published() is accessible from all kinds of querysets
        self.cursor.execute("select ID from %s order by post_date desc limit 2" % db_table)
        self.assertEqual(repr(BasePost.objects.values_list('id')[:2]), repr(list(self.cursor.fetchall())))
        self.cursor.execute("select ID from %s where post_status='publish' order by ID desc limit 2" % db_table)
        result = repr(list(self.cursor.fetchall()))
        self.assertEqual(repr(BasePost.objects.values_list('id').published()[:2]), result)
        self.assertEqual(repr(BasePost.objects.published().values_list('id')[:2]), result)
        ### test page ordering
        self.cursor.execute("select ID from %s where post_type='page' order by post_date desc limit 2" % db_table)
        self.assertEqual(repr(BasePost.objects.pages().values_list('id')[:2]), repr(list(self.cursor.fetchall())))
        
    def testDbTable(self):
        db_table1 = BasePost._meta.db_table
        self.cursor.execute("select count(*) from %s" % db_table1)
        num1 = self.cursor.fetchone()[0]
        blog = Blog.factory(2)
        db_table2 = BasePost._meta.db_table
        self.assertNotEqual(db_table1, db_table2)
        self.cursor.execute("select count(*) from %s" % db_table2)
        num2 = self.cursor.fetchone()[0]
        self.assertNotEqual(num1, num2)
        self.assertEqual(BasePost.objects.count(), num2)
        Blog.default_active()

    def testPermalink(self):
        self.assertEqual(
            BasePost.objects.posts().published()[0].get_absolute_url(),
            '/first-category/28-post-in-first-category-2/'
        )
        self.assertEqual(
            BasePost.objects.pages().published()[0].get_absolute_url(),
            '/another-page/'
        )
        
    def testExcerpt(self):
        self.assertEqual(
            BasePost.objects.posts().published()[0].excerpt,
            u'Once more.'
        )
        
    def testMore(self):
        post = BasePost.objects.get(id=5)
        self.assertTrue(post.more)
        
    def testPostMeta(self):
        post = BasePost.objects.get(id=5)
        self.assertTrue(post.postmeta_set.count() > 0)
        