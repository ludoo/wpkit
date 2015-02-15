import re
import unittest

from django.conf import settings
from django.db import connection
from django.core.urlresolvers import set_urlconf
from django.test.client import Client

from wp_frontman.blog import Blog
from wp_frontman.models import Post


class PostAttachmentsTestCase(unittest.TestCase):
    
    def setUp(self):
        self.root_urlconf = settings.ROOT_URLCONF
        settings.ROOT_URLCONF = Blog.get_active().urlconf
        self.cursor = connection.cursor()
        
    def tearDown(self):
        settings.ROOT_URLCONF = self.root_urlconf
        
    def testBootstrap(self):
        posts = list(Post.objects.published())
        Post._bootstrap_attachments(posts)
        for p in posts:
            if p.id in (5, 19, 21):
                self.assertTrue(p.featured_image, "%s %s" % (p.id, p.featured_image))
                if p.id == 21:
                    self.assertFalse(p.attachments, p.id)
            elif not 'attachments' in p._cache:
                raise ValueError("Missing attachments for post %s" % p.id)

    def testAttachments(self):
        post = Post.objects.get(id=5)
        self.assertEqual(post.featured_image['path'], '/wp-content/uploads/2011/03/dp2-2.jpg')
        self.assertEqual([a['attachment_post_id'] for a in post.attachments], [32, 34])
        self.assertEqual([a['sizes'].keys() for a in post.attachments], [['medium', 'thumbnail'], ['medium', 'thumbnail']])
        self.assertEqual(post.thumbnail, {'width': '150', 'path': '/wp-content/uploads/2011/03/dp2-2-150x150.jpg', 'file': 'dp2-2-150x150.jpg', 'height': '150'})
        post = Post.objects.get(id=21)
        self.assertEqual(post.featured_image['path'], '/wp-content/uploads/2011/03/dp2-1.jpg')
        self.assertFalse(post.attachments)
        self.assertEqual(post.thumbnail, {'width': '150', 'path': '/wp-content/uploads/2011/03/dp2-1-150x150.jpg', 'file': 'dp2-1-150x150.jpg', 'height': '150'})
        