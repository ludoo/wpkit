import unittest

from django.conf import settings
from django.db import connection

from wp_frontman.blog import Blog
from wp_frontman.models import Post, Term, TaxonomyTerm, PostTerms


class PostTaxonomyTestCase(unittest.TestCase):
    
    def setUp(self):
        self.root_urlconf = settings.ROOT_URLCONF
        settings.ROOT_URLCONF = Blog.get_active().urlconf
        self.cursor = connection.cursor()
        
    def tearDown(self):
        settings.ROOT_URLCONF = self.root_urlconf
        
    def testOptions(self):
        Blog.factory(1)
        db_tables_1 = (Term._meta.db_table, TaxonomyTerm._meta.db_table, PostTerms._meta.db_table)
        Blog.factory(2)
        db_tables_2 = (Term._meta.db_table, TaxonomyTerm._meta.db_table, PostTerms._meta.db_table)
        for a, b in zip(db_tables_1, db_tables_2):
            self.assertNotEqual(a, b)
        Blog.default_active()

    def testPostTaxonomy(self):
        p = Post.objects.published()[0]
        # test that the related manager works
        self.assertEqual(
            sorted([(t.id, t.taxonomy, t.term.name) for t in p.base_taxonomy.select_related('term')]),
            [(1L, u'category', u'Uncategorized'), (3L, u'category', u'First category'), (10L, u'post_tag', u'tag1'), (11L, u'post_tag', u'tag2'), (12L, u'post_tag', u'tag3'), (16L, u'test', u'Test Taxonomy 1.1')]
        )
        q = """
            select t.term_id, t.taxonomy, tm.name
            from wp_posts p
            inner join wp_term_relationships r on r.object_id=p.ID
            inner join wp_term_taxonomy t on t.term_taxonomy_id=r.term_taxonomy_id
            inner join wp_terms tm on tm.term_id=t.term_id
            where p.ID=%s %%s
            order by tm.name
        """ % p.id
        # test that taxonomy returns all terms in the correct order
        self.cursor.execute(q % '')
        _terms = self.cursor.fetchall()
        terms = tuple(p.base_taxonomy.values_list('term_id', 'taxonomy', 'term__name'))
        self.assertEqual(_terms, terms)
        # test that categories returns all categories in the correct order
        self.cursor.execute(q % "and t.taxonomy='category'")
        _categories = self.cursor.fetchall()
        self.assertEqual(_categories, tuple((c.term_id, c.taxonomy, c.term.name) for c in p.categories))
        self.assertEqual(_categories, tuple((c.term_id, c.taxonomy, c.term.name) for c in p.category_set.select_related('term')))
        # now check tags, and that we are not issuing one more query
        self.cursor.execute(q % "and t.taxonomy='post_tag'")
        _tags = self.cursor.fetchall()
        from django.conf import settings
        settings.DEBUG = True
        _num = len(connection.queries)
        self.assertEqual(_tags, tuple((c.term.id, c.taxonomy, c.term.name) for c in p.tags))
        self.assertEqual(_tags, tuple((c.term.id, c.taxonomy, c.term.name) for c in p.tag_set.select_related('term')))
        self.assertEqual(_num+1, len(connection.queries))
        # now test that Post.fill_taxonomy_cache works and uses a single query
        posts = list(Post.objects.posts().published()[:5])
        _num = len(connection.queries)
        self.assertTrue(_num != 0)
        Post.fill_taxonomy_cache(posts)
        self.assertEqual(_num + 1, len(connection.queries))
        _num = len(connection.queries)
        self.assertTrue(all(p.categories for p in posts))
        self.assertEqual(_num, len(connection.queries))
        settings.DEBUG = False
        