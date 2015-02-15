import unittest

from django.conf import settings
from django.db import connection
from django.test.client import Client

from wp_frontman.blog import Blog
from wp_frontman.models import Term, Category, Tag, TaxonomyTerm, PostTerms, PostCategories, PostTags


class TaxonomiesTestCase(unittest.TestCase):
    
    def setUp(self):
        self.cursor = connection.cursor()
        
    def testTaxonomyTerm(self):
        self.cursor.execute("select object_id from wp_term_relationships where term_taxonomy_id=13")
        post_ids = [r[0] for r in self.cursor.fetchall()]
        _post_ids = [p.post_id for p in PostTags.objects.filter(tag=Tag.objects.get(id=13))]
        self.assertEqual(post_ids, _post_ids)
        
    def testCategory(self):
        self.cursor.execute("select object_id from wp_term_relationships where term_taxonomy_id=5")
        post_ids = [r[0] for r in self.cursor.fetchall()]
        _post_ids = [p.post_id for p in PostCategories.objects.filter(category=Category.objects.get(id=5))]
        self.assertEqual(post_ids, _post_ids)
        parent = Category.objects.get(id=3)
        child = Category.objects.select_related('term').get(id=7)
        self.assertEqual(parent, child.parent)
        self.assertEqual(child.get_absolute_url(), '/category/first-category/first-category-second-child/')
        self.assertEqual(Category.objects.get(term__slug=child.term.slug), child)
        
    def testParents(self):
        self.cursor.execute("""
            select
            ttp.term_taxonomy_id, tp.name, ttp.taxonomy,
            tt.term_taxonomy_id, t.name, tt.taxonomy
            from wp_term_taxonomy tt
            inner join wp_terms t on t.term_id=tt.term_id
            left join wp_terms tp on tp.term_id=tt.parent
            left join wp_term_taxonomy ttp on ttp.term_id=tp.term_id
            where tt.taxonomy='category' and (ttp.taxonomy is null or ttp.taxonomy=tt.taxonomy)
        """)
        _categories = sorted(self.cursor.fetchall())
        # without select related
        categories = sorted([
            (
                None if not c.parent_id else c.parent.id,
                None if not c.parent_id else c.parent.term.name,
                None if not c.parent_id else c.parent.taxonomy,
                c.id, c.term.name, c.taxonomy
            ) for c in Category.objects.all()
        ])
        self.assertEqual(_categories, categories)
        # with select related on terms
        categories = sorted([
            (
                None if not c.parent_id else c.parent.id,
                None if not c.parent_id else c.parent.term.name,
                None if not c.parent_id else c.parent.taxonomy,
                c.id, c.term.name, c.taxonomy
            ) for c in Category.objects.select_related('term')
        ])
        self.assertEqual(_categories, categories)
        # with select related on parent
        categories = sorted([
            (
                None if not c.parent_id else c.parent.id,
                None if not c.parent_id else c.parent.term.name,
                None if not c.parent_id else c.parent.taxonomy,
                c.id, c.term.name, c.taxonomy
            ) for c in Category.objects.select_related('parent')
        ])
        self.assertEqual(_categories, categories)
        