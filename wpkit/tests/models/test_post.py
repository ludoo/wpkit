import sys
import logging
import datetime

from django.test import TestCase
from django_nose.tools import *
from django.conf import settings
from django.db import connection
from django.core.urlresolvers import set_urlconf

from wpkit.models import Site
from wpkit.wp.options import WPPostMeta


assert_equal.im_class.maxDiff = None


class TestWPPost(TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.blog = Site.objects.get_default().get_blog(1)
        cls.models = cls.blog.models

    def test_manager_post_types(self):
        manager = self.models.Post.objects
        assert_true(all(
            hasattr(manager, post_type+'s') for post_type in self.blog.post_types
        ))

    def test_all(self):
        qs = self.models.Post.objects.posts().select_related('author')
        cursor = connection.cursor()
        cursor.execute("""
            select p.id, nullif(p.post_parent, '0'), p.post_date, p.post_type, p.post_name, u.user_login
            from wp_posts p
            inner join wp_users u on u.id=p.post_author
            where p.post_type='post'
            order by p.post_date desc, p.id
        """)
        assert_equals(
            tuple((p.id, p.parent_id, p.date, p.post_type, p.slug, p.author.login) for p in qs),
            cursor.fetchall()
        )

    def test_pages(self):
        qs = self.models.Post.objects.pages().select_related('author')
        cursor = connection.cursor()
        cursor.execute("""
            select p.id, nullif(p.post_parent, '0'), p.post_date, p.post_type, p.post_name, u.user_login
            from wp_posts p
            inner join wp_users u on u.id=p.post_author
            where p.post_type='page'
            order by p.post_date desc, p.id
        """)
        assert_equals(
            tuple((p.id, p.parent_id, p.date, p.post_type, p.slug, p.author.login) for p in qs),
            cursor.fetchall()
        )

    def test_postmeta(self):
        post = self.models.Post.objects.get(slug='post-1-standard')
        cursor = connection.cursor()
        cursor.execute("select meta_id, meta_key, meta_value from wp_postmeta where post_id=%s", (post.id,))
        result = cursor.fetchall()
        assert_equals(
            tuple(post.postmeta_set.values_list('id', 'key', 'value')),
            result
        )
        meta = post.meta
        assert_true(isinstance(meta, WPPostMeta))
        for m in result:
            assert_equals(getattr(meta, m[1]), m[2])

    def test_taxonomies_rel(self):
        cursor = connection.cursor()
        cursor.execute("""
            select p.id, p.post_name, t.term_taxonomy_id, t.taxonomy, tt.name
            from wp_term_relationships r
            inner join wp_posts p on p.id=r.object_id
            inner join wp_term_taxonomy t on t.term_taxonomy_id=r.term_taxonomy_id
            inner join wp_terms tt on tt.term_id=t.term_id
            where p.post_status='publish'
            order by r.object_id, r.term_taxonomy_id
        """)
        assert_equals(
            tuple(self.models.PostTermRelationship.objects.select_related(
                'post', 'taxonomy', 'taxonomy__term'
            ).filter(post__status='publish').order_by(
                'post_id', 'taxonomy_id'
            ).values_list(
                'post__id', 'post__slug', 'taxonomy__id', 'taxonomy__taxonomy', 'taxonomy__term__name'
            )),
            cursor.fetchall()
        )
        cursor.execute("""
            select t.term_taxonomy_id, t.taxonomy, tt.name
            from wp_term_relationships r
            inner join wp_term_taxonomy t on t.term_taxonomy_id=r.term_taxonomy_id
            inner join wp_terms tt on tt.term_id=t.term_id
            where r.object_id=14
            order by r.term_taxonomy_id
        """)
        post = self.models.Post.objects.get(id=14)
        assert_equals(
            tuple(post.taxonomies_rel.select_related(
                'taxonomy', 'taxonomy__term'
            ).order_by('id').values_list(
                'id', 'taxonomy', 'term__name'
            )),
            cursor.fetchall()
        )

    def test_taxonomies_filters(self):
        post = self.models.Post.objects.get(id=14)
        settings.DEBUG = True
        num_queries = len(connection.queries)
        cursor = connection.cursor()
        cursor.execute("""
            select t.taxonomy, tt.name
            from wp_term_relationships r
            inner join wp_term_taxonomy t on t.term_taxonomy_id=r.term_taxonomy_id
            inner join wp_terms tt on tt.term_id=t.term_id
            where r.object_id=14 and t.taxonomy='category'
            order by r.term_taxonomy_id
        """)
        assert_equals(
            cursor.fetchall(),
            tuple((t.taxonomy, t.term.name) for t in post.categories)
        )
        assert_equals(
            post.categories[0],
            post.category
        )
        cursor.execute("""
            select t.taxonomy, tt.name
            from wp_term_relationships r
            inner join wp_term_taxonomy t on t.term_taxonomy_id=r.term_taxonomy_id
            inner join wp_terms tt on tt.term_id=t.term_id
            where r.object_id=14 and t.taxonomy='post_format'
            order by r.term_taxonomy_id
        """)
        assert_equals(
            cursor.fetchall(),
            tuple((t.taxonomy, t.term.name) for t in post.formats)
        )
        assert_equals(
            post.formats[0],
            post.format
        )
        assert_equals(len(connection.queries), num_queries+3)
        settings.DEBUG = False
        post = self.models.Post.objects.get(id=22)
        cursor.execute("""
            select t.taxonomy, tt.name
            from wp_term_relationships r
            inner join wp_term_taxonomy t on t.term_taxonomy_id=r.term_taxonomy_id
            inner join wp_terms tt on tt.term_id=t.term_id
            where r.object_id=22 and t.taxonomy='post_tag'
            order by r.term_taxonomy_id
        """)
        assert_equals(
            cursor.fetchall(),
            tuple((t.taxonomy, t.term.name) for t in post.tags)
        )
        assert_equals(
            post.tags[0],
            post.tag
        )
        
    def test_prefetch_related(self):
        settings.DEBUG = True
        num_queries = len(connection.queries)
        # published_posts forces prefetch_related
        posts = list(self.models.Post.objects.published_posts().order_by('id'))
        cursor = connection.cursor()
        cursor.execute("""
            select r.object_id, t.taxonomy, tt.name
            from wp_term_relationships r
            inner join wp_term_taxonomy t on t.term_taxonomy_id=r.term_taxonomy_id
            inner join wp_terms tt on tt.term_id=t.term_id
            where r.object_id in (%s)
            order by r.object_id, tt.term_order, tt.name
        """ % ','.join(str(p.id) for p in posts))
        expected = cursor.fetchall()
        result = tuple((p.id, t.taxonomy, t.term.name) for p in posts for t in p.taxonomies_rel.all())
        assert_equals(result, expected)
        assert_equals(len(connection.queries), num_queries+3)
        settings.DEBUG = False
        
    def test_url_args(self):
        post = self.models.Post.objects.get(slug='post-1-standard')
        ps_tokens = post._wp_blog.ps_tokens
        d = post.date
        assert_equals(post.url_args, {
            'slug': post.slug, 'month': d.strftime('%m'),
            'day': d.strftime('%d'), 'year': d.strftime('%Y')
        })
        post._wp_blog.__dict__['ps_tokens'] = ('id', 'author')
        assert_equals(post.url_args, {
            'author':post.author.nicename, 'id':post.id
        })
        post._wp_blog.__dict__['ps_tokens'] = ('id', 'category')
        assert_equals(post.url_args, {
            'category':'Category 1.1', 'id':12
        })
        post._wp_blog.__dict__['ps_tokens'] = ps_tokens
        
    def test_permalink(self):
        post = self.models.Post.objects.get(slug='post-1-standard')
        set_urlconf(post._wp_blog.urlconf)
        try:
            assert_equals(
                post.get_absolute_url(),
                '/2014/10/06/post-1-standard/'
            )
            assert_equals(
                post.permalink,
                'http://spritz.localtest.me/2014/10/06/post-1-standard/'
            )
        finally:
            set_urlconf(None)

    def test_more(self):
        post = self.models.Post(content='Some random stuff')
        assert_false(post.has_more)
        assert_equals(post.content_leader, post.content)
        assert_true(post.content_trailer is None)
        post = self.models.Post(content='Some random stuff with a more <!--more--> tag')
        assert_true(post.has_more)
        assert_equals(post.content_leader, post.content[:post.content.find('<!--more-->')])
        assert_equals(post.content_trailer, post.content[len(post.content_leader)+11:])

    def test_archives(self):
        cursor = connection.cursor()
        cursor.execute("""
            select date_format(post_date, '%Y %m') as d, count(id)
            from wp_posts
            where post_type='post' and post_status='publish'
            group by d
            order by d desc
        """)
        archive_dates = self.models.Post.objects.posts().published().monthly_archives()
        assert_equals(
            tuple((d['date'].strftime('%Y %m'), d['num_posts']) for d in archive_dates),
            cursor.fetchall()
        )
        cursor.execute("""
            select date_format(post_date, '%Y %m') as d, count(id)
            from wp_posts
            group by d
            order by d desc
        """)
        archive_dates = self.models.Post.objects.monthly_archives()
        assert_equals(
            tuple((d['date'].strftime('%Y %m'), d['num_posts']) for d in archive_dates),
            cursor.fetchall()
        )
        cursor.execute("""
            select date_format(post_date, '%Y') as d, count(id)
            from wp_posts
            where post_type='post' and post_status='publish'
            group by d
            order by d desc
        """)
        archive_dates = self.models.Post.objects.posts().published().yearly_archives()
        assert_equals(
            tuple((d['date'].strftime('%Y'), d['num_posts']) for d in archive_dates),
            cursor.fetchall()
        )

    def test_comments(self):
        cursor = connection.cursor()
        cursor.execute("""
            select comment_id
            from wp_comments
            where comment_post_id=12 and comment_type='' and comment_approved='1'
        """)
        sql_comments = [r[0] for r in cursor.fetchall()]
        post = self.models.Post.objects.get(id=12)
        assert_equals(
            len(sql_comments),
            post.comment_set.comments().approved().count()
        )
        assert_equals(
            len(sql_comments),
            post.comment_count
        )
        assert_equals(
            sql_comments,
            [r[0] for r in post.comment_set.comments().approved().values_list('id')]
        )
        