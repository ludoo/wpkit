import sys
import logging

from django.db import connection
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django_nose.tools import *

from wpkit.models import Site, DB_PREFIX


logger = logging.getLogger('wpkit.test.models_wp_taxonomy')


class TestWPTaxonomy(TestCase):
    
    @classmethod
    def setUpClass(cls):
        site = Site.objects.get_default()
        cls.models_1 = site.get_blog(1).models
        cls.models_3 = site.get_blog(3).models

    def test_terms(self):
        cursor = connection.cursor()
        cursor.execute("select * from wp_terms order by term_order, name")
        assert_equals(
            tuple(self.models_1.TaxonomyTerm.objects.values_list()),
            cursor.fetchall()
        )
        cursor.execute("select * from wp_3_terms order by name")
        assert_equals(
            tuple(self.models_3.TaxonomyTerm.objects.values_list()),
            cursor.fetchall()
        )
        
    def test_taxonomy(self):
        _debug, settings.DEBUG = settings.DEBUG, True
        settings.DEBUG = True
        cursor = connection.cursor()
        cursor.execute("""
            select tt.term_taxonomy_id, tt.taxonomy, t.name
            from wp_term_taxonomy tt
            inner join wp_terms t on t.term_id=tt.term_id
            order by t.term_order, t.name
        """)
        num_queries = len(connection.queries)
        blog1_qs = self.models_1.Taxonomy.objects.values_list(
            'id', 'taxonomy', 'term__name'
        )
        assert_equals(
            tuple(blog1_qs),
            cursor.fetchall()
        )
        assert_equals(len(connection.queries), num_queries+1)
        settings.DEBUG = _debug
        
    def test_taxonomy_manager(self):
        categories = list(self.models_1.Taxonomy.objects.categories())
        assert_equals(len(categories), 3)
        assert_true(all(c.taxonomy == 'category' for c in categories))
        
    def test_taxonomy_posts(self):
        taxonomy = self.models_1.Taxonomy.objects.get(
            taxonomy='category', term__slug='category-1'
        )
        cursor = connection.cursor()
        cursor.execute(
            "select object_id from wp_term_relationships where term_taxonomy_id=%s",
            (taxonomy.id,)
        )
        expected = sorted([r[0] for r in cursor.fetchall()])
        qs = taxonomy.posts.filter(post_type='post', status='publish')
        result = sorted([r[0] for r in qs.values_list('id')])
        assert_equals(expected, result)
