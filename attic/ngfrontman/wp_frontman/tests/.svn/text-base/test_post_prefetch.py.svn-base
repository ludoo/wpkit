import unittest

from django.db import connections

from wp_frontman.models import Site, Blog
from wp_frontman.tests.utils import MultiBlogMixin


class PostPrefetchTestCase(MultiBlogMixin, unittest.TestCase):

    def setUp(self):
        super(PostPrefetchTestCase, self).setUp()
        self.cursor = connections['test'].cursor()
        self.cursor_mu = connections['test_multi'].cursor()
        
    def testPrefetchTaxonomy(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        post = blog.models.BasePost.objects.get(id=13)
        not_prefetched = post.taxonomies
        self.assertTrue(not_prefetched)
        post = blog.models.BasePost.objects.filter(id=13).prefetch_taxonomies()[0]
        num_queries = len(connections['test'].queries)
        prefetched = post.taxonomies
        self.assertTrue(prefetched)
        self.assertEqual(not_prefetched, prefetched)
        self.assertEqual(len(connections['test'].queries), num_queries)

    def testPrefetchChildren(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        post = blog.models.BasePost.objects.get(id=13)
        not_prefetched = post.children
        self.assertTrue(not_prefetched)
        post = blog.models.BasePost.objects.filter(id=13).prefetch_children()[0]
        num_queries = len(connections['test'].queries)
        prefetched = post.children
        self.assertTrue(prefetched)
        self.assertEqual(not_prefetched, prefetched)
        self.assertEqual(len(connections['test'].queries), num_queries)

    def testPrefetchAttachments(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        post = blog.models.BasePost.objects.get(id=13)
        not_prefetched = post.attachments
        self.assertTrue(not_prefetched)
        post = blog.models.BasePost.objects.filter(id=13).prefetch_attachments()[0]
        num_queries = len(connections['test'].queries)
        prefetched = post.attachments
        self.assertTrue(prefetched)
        self.assertEqual(not_prefetched, prefetched)
        self.assertEqual(len(connections['test'].queries), num_queries)
        