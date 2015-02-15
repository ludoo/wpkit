# encoding: utf8

from django.conf import settings
from django.test import TestCase
from django_nose.tools import *

from wpkit.wp.permalinks import process_permalink, wp_urlpatterns, BASES


"""
%year%      The year of the post, four digits, for example 2004
%monthnum%  Month of the year, for example 05
%day%       Day of the month, for example 28
%hour%      Hour of the day, for example 15
%minute%    Minute of the hour, for example 43
%second%    Second of the minute, for example 33
%post_id%   The unique ID # of the post, for example 423
%postname%  Post slug field on Edit Post/Page panel). So “This Is A Great Post!” becomes this-is-a-great-post in the URI.
%category%  Category slug field on New/Edit Category panel). Nested sub-categories appear as nested directories in the URI.
%author%    A sanitized version of the author name.
"""

class TestPermalinks(TestCase):
    
    TESTS = (
        ('/%year%/%monthnum%/%day%/%postname%/', (
            ('year', 'month', 'day', 'slug'),
            '(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})/(?P<slug>[^/]+)'
        )),
        ('/archives/%post_id%', (
            ('id',),
            'archives/(?P<id>[0-9]+)'
        )),
    )
    
    @classmethod
    def setUpClass(cls):
        pass
    
    def test_fail(self):
        assert_raises_regexp(ValueError, r'^Permalink structure cannot be empty or null$', process_permalink, '')
        
    def test_structures(self):
        for option, expected in self.TESTS:
            result = process_permalink(option)
            assert_equals(result, expected)

    def test_urlpatterns(self):
        
        patterns = wp_urlpatterns('/abc/', '(?P<id>[0-9]+)', {})
        
        assert_true(all(len(p) == 4 for p in patterns))
        assert_equals(len(patterns), 27)
        
        all_names = sorted(set(p[-1][6:] for p in patterns))
        
        assert_equals(
            all_names,
            [
                'archive', 'attachment', 'author', 'category', 'favicon',
                'feed', 'feed_comments', 'index', 'media', 'page', 'post',
                'post_format', 'post_tag', 'robots', 'search'
            ]
        )
        
        assert_equals(
            sorted(set(p[-1][6:] for p in patterns if not p[0].startswith('^abc/'))),
            ['favicon', 'robots']
        )
        
        assert_equals(
            sorted(set(all_names).difference(
                sorted(set(p[-1][6:] for p in patterns if BASES['pagination'] in p[0]))
            )),
            ['attachment', 'favicon', 'feed', 'feed_comments', 'media', 'page', 'post', 'robots']
        )
        
    def test_urlpatterns_custom_bases(self):
        
        patterns = wp_urlpatterns('/abc/', '(?P<id>[0-9]+)', {'author':'autore', 'category':'categoria'})
        
        assert_true(all(len(p) == 4 for p in patterns))
        assert_equals(len(patterns), 27)
        
        category_patterns = [p for p in patterns if 'categoria' in p[0]]
        assert_equals(len(category_patterns), 4)
        assert_equals(set(p[-1][6:] for p in category_patterns), set(['category']))

        author_patterns = [p for p in patterns if 'autore' in p[0]]
        assert_equals(len(author_patterns), 2)
        assert_equals(set(p[-1][6:] for p in author_patterns), set(['author']))
