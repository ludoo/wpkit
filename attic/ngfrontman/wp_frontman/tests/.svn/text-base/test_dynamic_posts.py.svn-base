import unittest

from django.db import connections

from wp_frontman.models import Site, Blog
from wp_frontman.tests.utils import MultiBlogMixin


class DynamicPostsTestCase(MultiBlogMixin, unittest.TestCase):

    def setUp(self):
        super(DynamicPostsTestCase, self).setUp()
        self.cursor = connections['test'].cursor()
        self.cursor_mu = connections['test_multi'].cursor()
    
    def testSingle(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        self.assertTrue(len(blog.models.BasePost._wp_post_types) > 0)
        self.cursor.execute(
            "select ID, post_type from %s order by ID" % blog.models.BasePost._meta.db_table
        )
        posts = [(blog.models.BasePost._wp_post_types.get(r[1], blog.models.BasePost).__name__, r[0], r[1]) for r in self.cursor.fetchall()]
        self.assertEqual(
            [(p.__class__.__name__, p.id, p.post_type) for p in blog.models.BasePost.objects.order_by('id')],
            posts
        )

    def testPostSingle(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        self.cursor.execute(
            "select ID, post_name, post_type, post_type from %s where post_type='post' order by ID" % (blog.models.Post._meta.db_table)
        )
        self.assertEqual(
            [(p.id, p.slug, p.post_type, p._wp_post_type) for p in blog.models.Post.objects.order_by('id')],
            list(self.cursor.fetchall())
        )
        
    def testPostAuthor(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        post = blog.models.Post.objects.select_related('author')[0]
        self.assertEqual(type(post.author), blog.site.models.User)
        self.cursor.execute("select post_author from %s where ID=%s" % (blog.models.Post._meta.db_table, post.id))
        self.assertEqual(post.author.id, self.cursor.fetchone()[0])

    def testPostParent(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        post = blog.models.Post.objects.get(id=116)
        self.assertEqual(post.parent_id, None)
        self.assertEqual(post.parent, None)
        
    """
    def testParentsSingle(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        p = blog.models.Post.objects.all()[0]
        self.assertTrue(not hasattr(p, 'parent_id'))
        p = blog.models.Attachment.objects.all()[0]
        self.assertTrue(hasattr(p, 'parent_id'))
        p = blog.models.Page.objects.select_related('parent').order_by('-id')[0]
        self.assertTrue(hasattr(p, 'parent_id'))
        self.assertTrue(type(p.parent), blog.models.Page)
    """
    