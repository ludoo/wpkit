import re

from django.db import connection
from django.core.paginator import Paginator, Page
from django.test import Client
from django_nose.tools import *

from . import TestView


class TestIndexView(TestView):
    
    @classmethod
    def setUpClass(cls):
        super(TestIndexView, cls).setUpClass()
        cls.response = Client(HTTP_HOST='spritz.localtest.me').get('/')
    
    def test_template(self):
        assert_equals(len(self.response.templates), 3)
        assert_equals(self.response.templates[0].name, 'wpkit/index.html')
        assert_true(
            '<!-- index.html template for blog 1 -->' in self.response.content
        )
        
    def test_context(self):
        context = self.response.context
        assert_true('page' in context)
        assert_equals(type(context['page']), Page)

    def test_invalid_page(self):
        response = Client(HTTP_HOST='spritz.localtest.me').get('/page/0/')
        assert_equals(response.templates[0].name, 'wpkit/index.html')
        assert_equals(response.context['page'], None)
        
    def test_valid_page(self):
        response = Client(HTTP_HOST='spritz.localtest.me').get('/page/1/')
        assert_true(len(re.findall(r'id="post\-[0-9]+"', response.content)) > 0)

    def test_posts_list(self):
        cursor = connection.cursor()
        cursor.execute("select option_value from wp_options where option_name='posts_per_page'")
        num_posts = cursor.fetchone()[0]
        cursor.execute("""
            select id from wp_posts
            where post_type='post' and post_status='publish'
            order by post_date_gmt desc limit %s
        """ % num_posts)
        post_ids = [r[0] for r in cursor.fetchall()]
        assert_true(all(
            ('id="post-%s"' % i) in self.response.content for i in post_ids
        ))
        
        