import unittest

from types import ModuleType

from django.db import connections

from wp_frontman.models import Site, Blog
from wp_frontman.tests.utils import MultiBlogMixin


class BlogTestCase(MultiBlogMixin, unittest.TestCase):
    
    def testFactory(self):
        self.reset_blog_class()
        blog = Blog(1)
        self.assertEqual(blog.blog_id, 1)
        self.assertEqual(id(blog), id(Blog(1)))
        self.assertEqual(Blog.get_active(), None)
        self.assertTrue(Blog.factory(1) is blog)
        self.assertEqual(Blog.get_active(), blog)
        self.assertEqual(blog.path, None)
        
    def testFactoryMu(self):
        # hack the site to test for multiblog
        self.reset_blog_class(mu=True)
        blog = Blog(1)
        self.assertEqual(blog.blog_id, 1)
        self.assertTrue(Blog.factory(1) is blog)
        self.assertEqual(Blog.get_active(), blog)
        self.assertEqual(blog.path, '/')
        self.assertEqual(len(list(Blog.get_blogs())), 3)
        self.assertTrue(blog is Blog(1, self.site_mu))
        self.assertFalse(blog is Blog(1, self.site))
        self.assertEqual(blog.options['siteurl'], 'http://mu.ludolo.it/')
        
    def testDynamicModels(self):
        self.reset_blog_class()
        blog = Blog(1)
        self.assertTrue(isinstance(blog.models, ModuleType))
        self.assertEqual([(u.id, u.login) for u in blog.models.User.objects.all()], [(1L, u'ludo'), (2L, u'editor'), (3L, u'user')])
        self.reset_blog_class(mu=True)
        blog_mu = Blog(1)
        self.assertTrue(blog is not blog_mu)
        self.assertTrue(blog.models is not blog_mu.models)
        self.assertNotEqual(id(blog.models.User), id(blog_mu.models.User))
        self.assertNotEqual(id(blog.models.User.objects), id(blog_mu.models.User.objects))
        um = blog.models.User.objects.get(id=1).usermeta_set.all()[0]
        self.assertTrue(isinstance(um, blog.models.UserMeta), "UserMeta '%s' instead of '%s'" % (type(um), blog.models.UserMeta))
        self.assertTrue(isinstance(blog_mu.models.User.objects.get(id=1).usermeta_set.all()[0], blog_mu.models.UserMeta))
        
    def testDynamicModelsMu(self):
        self.reset_blog_class(mu=True)
        blog = Blog(1)
        self.assertTrue(blog.site.mu)
        self.assertTrue(isinstance(blog.models, ModuleType))
        self.assertFalse(blog.models is Blog(1, self.site).models)
        self.assertFalse(blog.models is Blog(2).models)
        self.assertEqual([(u.id, u.login) for u in blog.models.User.objects.all()], [(1L, u'ludo'), (2L, u'ludotest4')])
        
    def testOptions(self):
        self.reset_blog_class()
        blog = Blog(1)
        self.assertTrue(isinstance(blog.options['capabilities'], dict))
        self.assertEqual(blog.options['capabilities']['edit_posts'], [u'contributor', u'administrator', u'editor', u'author'])
        self.assertEqual(blog.options['upload_path'], 'wp-content/uploads')
        self.assertEqual(blog.options['upload_abspath'], '/var/virtual/wp/wordpress/wp-content/uploads')
        self.assertEqual(blog.options['pingback_url'], 'http://ludolo.it/xmlrpc.php')

    def testOptionsMu(self):
        self.reset_blog_class(mu=True)
        blog = Blog(2)
        self.assertTrue(isinstance(blog.options['capabilities'], dict))
        self.assertEqual(blog.options['capabilities']['edit_posts'], [u'contributor', u'administrator', u'editor', u'author'])
        self.assertEqual(blog.options['upload_path'], 'wp-content/blogs.dir/2/files')
        self.assertEqual(blog.options['upload_abspath'], '/var/virtual/wp/wordpress-mu/wp-content/blogs.dir/2/files')
        self.assertEqual(blog.options['pingback_url'], 'http://mu.ludolo.it/blog2/xmlrpc.php')
        