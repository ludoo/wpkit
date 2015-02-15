import unittest

from wp_frontman.blog import Blog


class BlogTestCase(unittest.TestCase):
    
    def testSite(self):
        meta = Blog.site.meta
        self.assertTrue(isinstance(meta, dict) and meta)
        self.assertEqual(Blog.site.siteurl, 'http://ludolo.it/')
        try:
            Blog.site.dummy_key
        except AttributeError, e:
            self.assertEqual(e.args[0], "'Site' object has no attribute 'dummy_key'")
        self.assertEqual(Blog.site.subdomain_install, False)
        blogs = Blog.site.blogs
        self.assertTrue(isinstance(blogs, dict) and blogs)
        
    def testSiteBlogForPath(self):
        self.assertEqual(Blog.site.blog_for_path('/'), Blog.get_active())
        self.assertEqual(Blog.site.blog_for_path('/blog2/category/pippo/'), Blog.factory(2))
        Blog.default_active()
        
    def testBlog(self):
        blogs = Blog.site.blogs.keys()
        b1 = Blog.factory(blogs[0])
        b2 = Blog.factory(blogs[0])
        self.assertEqual(b1, b2)
        self.assertEqual(b1.db_prefix, Blog.get_active_db_prefix())
        self.assertEqual(b1.db_prefix, 'wp_')
        self.assertEqual(b1.domain, 'ludolo.it')
        self.assertEqual(b1.siteurl, 'http://ludolo.it/')
        b2 = Blog.factory(blogs[1])
        self.assertEqual(b2.db_prefix, 'wp_2_')
        self.assertEqual(b2.siteurl, 'http://ludolo.it/blog2/')
        self.assertEqual(b2.siteurl_mapped, 'http://qix.it/blog2/')
        Blog.default_active()
        
    def testWpPaths(self):
        # the test database uses subdomain installs
        blog = Blog.factory(2)
        self.assertEqual(blog.home, 'http://qix.it/blog2/')
        self.assertEqual(blog.siteurl, 'http://ludolo.it/blog2/')
        self.assertEqual(blog.favicon_path, '/wp-content/blogs.dir/2/favicon.ico')
        Blog.default_active()
