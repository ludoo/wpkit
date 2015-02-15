import unittest

from django.db import connections

from wp_frontman.models import Blog
from wp_frontman.tests.utils import MultiBlogMixin


class SiteTestCase(MultiBlogMixin, unittest.TestCase):
    
    def testSingleBlog(self):
        self.reset_blog_class()
        site = Blog.site #Site(mu=False)
        self.assertTrue(site.meta is not None)
        self.assertEqual(site.blog_data.keys(), [1])
        self.assertEqual(site.blog_data[1]['blog_id'], 1)
        self.assertEqual(site.meta['siteurl'], 'http://ludolo.it/')
        self.assertEqual(sorted(site.blog_path_map.items()), [('', 1L)])
        self.assertEqual(sorted(site.blog_domain_map.items()), [])
        self.assertEqual(Blog.find_blog_id(), 1)

    def testMultiBlog(self):
        self.reset_blog_class(mu=True)
        site = Blog.site #Site(using='test_multi', mu=True)
        self.assertTrue(site.meta is not None)
        self.assertEqual(site.blog_data.keys(), [1, 2, 3])
        self.assertEqual(site.blog_data[1], {'domain': u'mu.ludolo.it', 'blog_id': 1L, 'archived': u'0', 'lang_id': None, 'path': u'/', 'secondary_domain': None})
        self.assertEqual(site.meta['siteurl'], 'http://mu.ludolo.it/')
        self.assertEqual(sorted(site.blog_path_map.items()), [('', 1L), (u'blog2', 2L), (u'blog3', 3L)])
        self.assertEqual(sorted(site.blog_domain_map.keys()), ['mu.ludolo.it'])
        self.assertTrue(len(site.blog_domain_map), 1)
        self.assertEqual(Blog.find_blog_id(path=''), 1)
        self.assertEqual(Blog.find_blog_id(path='blog2'), 2)
        self.assertEqual(Blog.find_blog_id(), None)
        # fake a secondary domain
        site.blog_domain_map['qix.ludolo.it'] = 'mu.ludolo.it'
        try:
            blog_id = Blog.find_blog_id(domain='qix.it')
        except ValueError, e:
            self.assertEqual(e.args[0], 'mu.ludolo.it')
        