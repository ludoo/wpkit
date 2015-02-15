import unittest

from difflib import unified_diff

from django.db import connections

from wp_frontman.models import Site, Blog
from wp_frontman.tests.utils import MultiBlogMixin


class PostMetaTestCase(MultiBlogMixin, unittest.TestCase):

    def setUp(self):
        super(PostMetaTestCase, self).setUp()
        self.cursor = connections['test'].cursor()
        self.cursor_mu = connections['test_multi'].cursor()
        
    def testMeta(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        post = blog.models.BasePost.objects.get(id=13).attachments[0]
        self.assertEqual(post.id, 127)
        self.assertTrue(len(post.metadict.keys()) == 2 and 'attached_file' in post.metadict and 'attachment_metadata' in post.metadict)
        self.assertEqual(post.metadict['attached_file'], '/wp-content/uploads/2012/02/Polaroid_Land_Camera_100_IMGP1930_WP.jpg')
        self.assertEqual(
            post.metadict['attachment_metadata']['sizes']['medium']['url'],
            '/wp-content/uploads/2012/02/Polaroid_Land_Camera_100_IMGP1930_WP-300x224.jpg'
        )
