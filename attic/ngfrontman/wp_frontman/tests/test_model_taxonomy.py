import unittest

from django.db import connections

from wp_frontman.models import Site, Blog
from wp_frontman.tests.utils import MultiBlogMixin


class TaxonomyTestCase(MultiBlogMixin, unittest.TestCase):
    
    def setUp(self):
        super(TaxonomyTestCase, self).setUp()
        self.cursor = connections['test'].cursor()
        self.cursor_mu = connections['test_multi'].cursor()
    
    def testTaxonomyTerm(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        self.cursor.execute(
            "select term_id, slug from %s order by term_id" % blog.models.TaxonomyTerm._meta.db_table
        )
        self.assertEqual(
            [(t.id, t.slug) for t in blog.models.TaxonomyTerm.objects.order_by('id')],
            list(self.cursor.fetchall())
        )
    
    def testTaxonomyTermMu(self):
        self.reset_blog_class(mu=True)
        blog = Blog(1)
        self.assertEqual([(t.id, t.slug) for t in blog.models.TaxonomyTerm.objects.order_by('slug')[:3]], [(2L, u'blogroll'), (30L, u'first-category'), (6L, u'first-category-first-child')])
    
    def testTaxonomy(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        self.cursor.execute(
            "select tt.term_taxonomy_id, tt.taxonomy, t.slug from %s tt inner join %s t on t.term_id=tt.term_id order by tt.term_taxonomy_id" % (
            blog.models.Taxonomy._meta.db_table, blog.models.TaxonomyTerm._meta.db_table)
        )
        self.assertEqual(
            [(t.id, t.taxonomy, t.term.slug) for t in blog.models.Taxonomy.objects.select_related('term').order_by('id')],
            list(self.cursor.fetchall())
        )
