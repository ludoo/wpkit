import unittest

from django.db import connections

from wp_frontman.models import Site, Blog
from wp_frontman.tests.utils import MultiBlogMixin


class DynamicTaxonomiesTestCase(MultiBlogMixin, unittest.TestCase):

    def setUp(self):
        super(DynamicTaxonomiesTestCase, self).setUp()
        self.cursor = connections['test'].cursor()
        self.cursor_mu = connections['test_multi'].cursor()
    
    def testSingle(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        self.assertTrue(len(blog.models.BasePostTaxonomy._wp_taxonomy_types) > 0)
        self.cursor.execute(
            "select taxonomy from %s order by term_taxonomy_id" % blog.models.Taxonomy._meta.db_table
        )
        taxonomies = [(blog.models.Taxonomy._wp_taxonomy_for_type.get(r[0], blog.models.Taxonomy).__name__, r[0], r[0]) for r in self.cursor.fetchall()]
        # non-public taxonomies have no specialized model, so they will be represented
        # by the generic Taxonomy model
        self.assertEqual(
            [(t.__class__.__name__, t.taxonomy, t._wp_taxonomy_types[0] if not isinstance(t, blog.models.Taxonomy) else t.taxonomy) for t in blog.models.Taxonomy.objects.order_by('id')],
            taxonomies
        )

    def testCategorySingle(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        self.cursor.execute(
            "select tt.term_taxonomy_id, t.slug from %s tt inner join %s t on t.term_id=tt.term_id where tt.taxonomy='category' order by tt.term_taxonomy_id" % (
            blog.models.Taxonomy._meta.db_table, blog.models.TaxonomyTerm._meta.db_table)
        )
        self.assertEqual(
            [(t.id, t.term.slug) for t in blog.models.Category.objects.select_related('term').order_by('id')],
            list(self.cursor.fetchall())
        )

    def testParentsSingle(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        c = blog.models.Category.objects.all()[0]
        self.assertTrue(hasattr(c, 'parent_id'))
        t = blog.models.PostTag.objects.all()[0]
        self.assertTrue(not hasattr(t, 'parent_id'))
        
    def testPropertiesSingle(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        # test that we have all the properties for builtin and custom taxonomies
        post = blog.models.Post
        for a in ('taxonomies', 'categories', 'post_tags', 'things'):
            p = getattr(post, a, None)
            self.assertTrue(p, "No property '%s' found in post %s: %s" % (a, post, dir(post)))
            self.assertTrue(isinstance(p, property), "Post '%s' is not a property but %s" % (a, p))
        # test that the Taxonomy models have the right taxonomy name set
        for a in ('category', 'post_tag', 'nav_menu', 'post_format', 'thing'):
            model_name = a.replace('_', ' ').title().replace(' ', '')
            model = getattr(blog.models, model_name)
            self.assertEqual(model._wp_taxonomy_name, a)
        # test that the properties actually use the prefetch related cache
        posts = blog.models.Post.objects.published().prefetch_taxonomies()[:3]
        num_queries = len(connections['test'].queries)
        for post in posts:
            self.assertTrue(post.taxonomies, "No taxonomies for post %s" % post.id)
            taxonomies = post.taxonomies
            for name, names in (('category', 'categories'), ('post_tag', 'post_tags'), ('thing', 'things')):
                result = getattr(post, names)
                self.assertTrue(isinstance(result, list), "Post.%s() for post %s returned %s" % (names, post.id, type(result)))
                objects = [t for t in taxonomies if t.taxonomy == name]
                if objects:
                    self.assertEqual(result, objects, "No %s for post %s, got %s from %s" % (names, post.id, result, [t.taxonomy for t in taxonomies]))
            self.assertEqual(len(connections['test'].queries), num_queries)
            
        