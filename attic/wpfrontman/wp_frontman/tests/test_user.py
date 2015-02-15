import unittest

from django.conf import settings
from django.db import connection

from wp_frontman.blog import Blog
from wp_frontman.models import User


class FakeRequest(object):
    COOKIES = dict(
        wordpress_logged_in_c23341c5aceca18dad49318bd9d228fe='ludo%7C1314613474%7C62be21ba58efe0f474b97935536d56e4'
    )
    

class UserTestCase(unittest.TestCase):
    
    def setUp(self):
        self.root_urlconf = settings.ROOT_URLCONF
        settings.ROOT_URLCONF = Blog.get_active().urlconf
        self.cursor = connection.cursor()
        self.u = User.objects.get(login='ludo')
        self.request = FakeRequest()
        
    def tearDown(self):
        settings.ROOT_URLCONF = self.root_urlconf
        
    def testUser(self):
        self.assertEqual(self.u.nicename, 'ludo')
        self.assertEqual(self.u.get_absolute_url(), '/author/ludo/')
        
    def testLoggedInCookie(self):
        self.assertEqual(User.login_from_cookie(FakeRequest(), 1314613400), ('ludo', 1314613474, '62be21ba58efe0f474b97935536d56e4'))
        request = FakeRequest()
        request.COOKIES = dict()
        user = User.user_from_cookie(request, *('ludo', 1314613474, '62be21ba58efe0f474b97935536d56e4'))
        self.assertTrue(isinstance(user, User))
        self.assertEqual(request.wp_user, user)
        self.assertEqual(user.nicename, 'ludo')
        
    def testNonce(self):
        request = FakeRequest()
        request.wp_user = User.objects.get(login='ludo')
        self.assertEqual(User.verify_nonce(request, '91e67416ee', 'wp_frontman', 1313413837), 1)
        
    def testUserMeta(self):
        self.assertFalse(self.u.first_name)
        
    def _testUserPosts(self):
        # posts, in any state
        self.cursor.execute("select count(*) from wp_posts where post_type='post' and post_author=%s" % self.u.id)
        self.assertEqual(self.u.basepost_set.posts().count(), self.cursor.fetchone()[0])
        # posts, published
        self.cursor.execute("select count(*) from wp_posts where post_type='post' and post_status='publish' and post_author=%s" % self.u.id)
        self.assertEqual(self.u.basepost_set.posts().published().count(), self.cursor.fetchone()[0])
        # pages, in any state
        self.cursor.execute("select count(*) from wp_posts where post_type='page' and post_author=%s" % self.u.id)
        self.assertEqual(self.u.basepost_set.filter(post_type='page').count(), self.cursor.fetchone()[0])
        # pages, published
        self.cursor.execute("select count(*) from wp_posts where post_type='page' and post_status='publish' and post_author=%s" % self.u.id)
        self.assertEqual(self.u.basepost_set.filter(post_type='page').published().count(), self.cursor.fetchone()[0])

    def testCapabilities(self):
        self.assertEqual(
            [u.id for u in User.objects.users_can('moderate_comments')],
            [1L]
        )
        
