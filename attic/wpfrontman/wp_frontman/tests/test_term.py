import unittest

from django.conf import settings
from django.db import connection
from django.test.client import Client

from wp_frontman.blog import Blog
from wp_frontman.models import Term, Tag


class TermTestCase(unittest.TestCase):
    
    def setUp(self):
        self.root_urlconf = settings.ROOT_URLCONF
        settings.ROOT_URLCONF = Blog.get_active().urlconf
        self.cursor = connection.cursor()
        
    def tearDown(self):
        settings.ROOT_URLCONF = self.root_urlconf
        
    def testManager(self):
        db_table = Term._meta.db_table
        self.cursor.execute("select count(*) from %s" % db_table)
        self.assertEqual(Term.objects.count(), self.cursor.fetchone()[0])
        
    def testQuotedSlug(self):
        client = Client(HTTP_HOST='ludolo.it')
        blog = Blog.factory(1)
        tag = Tag.objects.get(id=13)
        response = client.get(tag.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        Blog.default_active()

