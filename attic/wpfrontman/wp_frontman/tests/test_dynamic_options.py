import unittest

from wp_frontman.blog import Blog
from wp_frontman.models import Tag


class DynamicOptionsTestCase(unittest.TestCase):
    
    def testJoin(self):
        blog = Blog.factory(1)
        tag = Tag.objects.select_related('term').filter(term__name='tag1')
        blog = Blog.factory(2)
        tag = Tag.objects.select_related('term').filter(term__name='tag5')
        Blog.default_active()
