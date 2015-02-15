import unittest

from django.db import connections

from wp_frontman.models import Site, Blog
from wp_frontman.wp_helpers import month_archives, year_archives
from wp_frontman.tests.utils import MultiBlogMixin


class HelpersArchivesTestCase(MultiBlogMixin, unittest.TestCase):
    
    def setUp(self):
        super(HelpersArchivesTestCase, self).setUp()
        self.cursor = connections['test'].cursor()
        self.cursor_mu = connections['test_multi'].cursor()

    def testMonthlyArchives(self):
        self.reset_blog_class()
        blog = Blog(1)
        self.cursor.execute("""
            select distinct date_format(post_date, '%%Y %%m') as monthly_archive
            from %s
            where post_type='post' and post_status='publish'
            order by monthly_archive desc
        """ % blog.models.Post._meta.db_table)
        archive_dates = [tuple(map(int, r[0].split())) for r in self.cursor.fetchall()]
        archives = month_archives(blog)
        self.assertEqual(archive_dates, [(a['year'], a['month']) for a in archives])
        self.assertEqual(archives[0]['get_absolute_url'], '/%02i/%02i/' % archive_dates[0])
        
    def testYearlyArchives(self):
        self.reset_blog_class()
        blog = Blog(1)
        self.cursor.execute("""
            select distinct year(post_date) as y
            from %s
            where post_type='post' and post_status='publish'
            order by y desc
        """ % blog.models.Post._meta.db_table)
        archive_dates = [r[0] for r in self.cursor.fetchall()]
        archives = year_archives(blog)
        self.assertEqual(archive_dates, [a['year'] for a in archives])
        self.assertEqual(archives[0]['get_absolute_url'], '/%02i/' % archive_dates[0])
