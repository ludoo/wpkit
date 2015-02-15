import unittest

from django.db import connections

from wp_frontman.models import Site, Blog
from wp_frontman.tests.utils import MultiBlogMixin


class UserTestCase(MultiBlogMixin, unittest.TestCase):
    
    def testUser(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        self.assertEqual([(u.id, u.login) for u in blog.site.models.User.objects.all()], [(1L, u'ludo'), (2L, u'editor'), (3L, u'user')])
    
    def testUserMu(self):
        self.reset_blog_class(mu=True)
        blog = Blog(1)
        self.assertEqual([(u.id, u.login) for u in blog.site.models.User.objects.all()], [(1L, u'ludo'), (2L, u'ludotest4')])
    
    def testUserMeta(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        user = blog.site.models.User.objects.get(id=1)
        self.assertTrue(user._meta is None)
        self.assertTrue(len(user.meta) > 0 and user.meta is user._meta)
        for m in user.meta:
            self.assertEqual(m.user_id, user.id)
            self.assertTrue(m.user.__class__ is user.__class__)

    def testUserMetaMu(self):
        self.reset_blog_class(mu=True)
        blog = Blog(1)
        user = blog.site.models.User.objects.get(id=1)
        self.assertTrue(user._meta is None)
        self.assertTrue(len(user.meta) > 0 and user.meta is user._meta)
        for m in user.meta:
            self.assertEqual(m.user_id, user.id)
            self.assertTrue(m.user.__class__ is user.__class__)

    # TODO: move to the blog tests once we have implemented the users_can method in the Blog model
    #def testManager(self):
    #    self.reset_blog_class(mu=False)
    #    blog = Blog(1)
    #    self.assertEqual([u.id for u in blog.site.models.User.objects.users_can('edit_posts')], [1, 2])

    #def testManagerMu(self):
    #    self.reset_blog_class(mu=True)
    #    blog = Blog(1)
    #    self.assertEqual([u.id for u in blog.site.models.User.objects.users_can('edit_posts')], [1])
