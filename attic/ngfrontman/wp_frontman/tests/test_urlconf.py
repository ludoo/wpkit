import unittest

from django.core.urlresolvers import set_urlconf, reverse

from wp_frontman.models import Site, Blog
from wp_frontman.tests.utils import MultiBlogMixin


class UrlconfTestCase(MultiBlogMixin, unittest.TestCase):
    
    def testSingle(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        set_urlconf(blog.urlconf)
        # home
        self.assertEqual(reverse('wpf_index'), '/')
        self.assertEqual(reverse('wpf_index', kwargs=dict(page=2)), '/page/2/')
        # feed
        self.assertEqual(reverse('wpf_feed'), '/feed/')
        # category
        self.assertEqual(reverse('wpf_category', kwargs=dict(slug='stuff')), '/category/stuff/')
        self.assertEqual(reverse('wpf_category', kwargs=dict(slug='stuff', page=2)), '/category/stuff/page/2/')
        self.assertEqual(reverse('wpf_category', kwargs=dict(hierarchy='stuff/', slug='morestuff')), '/category/stuff/morestuff/')
        self.assertEqual(reverse('wpf_category', kwargs=dict(hierarchy='stuff/', slug='morestuff', page=2)), '/category/stuff/morestuff/page/2/')
        # tag
        self.assertEqual(reverse('wpf_tag', kwargs=dict(slug='stuff')), '/tag/stuff/')
        self.assertEqual(reverse('wpf_tag', kwargs=dict(slug='stuff', page=2)), '/tag/stuff/page/2/')
        # custom taxonomies
        self.assertEqual(reverse('wpf_thing', kwargs=dict(slug='stuff')), '/thing/stuff/')
        self.assertEqual(reverse('wpf_thing', kwargs=dict(slug='stuff', page=2)), '/thing/stuff/page/2/')
        self.assertEqual(reverse('wpf_thing', kwargs=dict(hierarchy='stuff/', slug='morestuff')), '/thing/stuff/morestuff/')
        self.assertEqual(reverse('wpf_thing', kwargs=dict(hierarchy='stuff/', slug='morestuff', page=2)), '/thing/stuff/morestuff/page/2/')
        # archives
        self.assertEqual(reverse('wpf_archive', kwargs=dict(year=2012, month='02')), '/2012/02/')
        self.assertEqual(reverse('wpf_archive', kwargs=dict(year=2012, month='02', page=3)), '/2012/02/page/3/')
        self.assertEqual(reverse('wpf_archive', kwargs=dict(year=2012)), '/2012/')
        self.assertEqual(reverse('wpf_archive', kwargs=dict(year=2012, page=3)), '/2012/page/3/')
        # author
        self.assertEqual(reverse('wpf_author', kwargs=dict(slug='ludo')), '/author/ludo/')
        self.assertEqual(reverse('wpf_author', kwargs=dict(slug='ludo', page=2)), '/author/ludo/page/2/')
        # search
        self.assertEqual(reverse('wpf_search'), '/search/')
        self.assertEqual(reverse('wpf_search', kwargs=dict(q='something')), '/search/something/')
        self.assertEqual(reverse('wpf_search', kwargs=dict(q='something', page=2)), '/search/something/page/2/')
        # post formats
        self.assertEqual(reverse('wpf_post_format', kwargs=dict(post_format='gallery')), '/type/gallery/')
        self.assertEqual(reverse('wpf_post_format', kwargs=dict(post_format='gallery', page=2)), '/type/gallery/page/2/')
        # posts
        self.assertEqual(reverse('wpf_post', kwargs=dict(year=2012, month='02', slug='post-title')), '/2012/02/post-title/')
        self.assertEqual(reverse('wpf_post', kwargs=dict(year=2012, month='02', slug='post-title', page=2)), '/2012/02/post-title/comment-page-2/')
        # attachments
        self.assertEqual(reverse('wpf_attachment', kwargs=dict(year=2012, month='02', slug='post-title', attachment_slug='image-name')), '/2012/02/post-title/attachment/image-name/')
        self.assertEqual(reverse('wpf_attachment', kwargs=dict(year=2012, month='02', slug='post-title', attachment_slug='image-name', page=2)), '/2012/02/post-title/attachment/image-name/comment-page-2/')
        
        
    def testMu(self):
        self.reset_blog_class(mu=True)
        blog = Blog(2)
        set_urlconf(blog.urlconf)
        # home
        self.assertEqual(reverse('wpf_index'), '/blog2/')
        self.assertEqual(reverse('wpf_index', kwargs=dict(page=2)), '/blog2/page/2/')
        # feed
        self.assertEqual(reverse('wpf_feed'), '/blog2/feed/')
        # category
        self.assertEqual(reverse('wpf_category', kwargs=dict(slug='stuff')), '/blog2/categoria/stuff/')
        self.assertEqual(reverse('wpf_category', kwargs=dict(slug='stuff', page=2)), '/blog2/categoria/stuff/page/2/')
        self.assertEqual(reverse('wpf_category', kwargs=dict(hierarchy='stuff/', slug='morestuff')), '/blog2/categoria/stuff/morestuff/')
        self.assertEqual(reverse('wpf_category', kwargs=dict(hierarchy='stuff/', slug='morestuff', page=2)), '/blog2/categoria/stuff/morestuff/page/2/')
        # tag
        self.assertEqual(reverse('wpf_tag', kwargs=dict(slug='stuff')), '/blog2/tag/stuff/')
        self.assertEqual(reverse('wpf_tag', kwargs=dict(slug='stuff', page=2)), '/blog2/tag/stuff/page/2/')
        # custom taxonomies
        self.assertEqual(reverse('wpf_thing', kwargs=dict(slug='stuff')), '/blog2/thing/stuff/')
        self.assertEqual(reverse('wpf_thing', kwargs=dict(slug='stuff', page=2)), '/blog2/thing/stuff/page/2/')
        self.assertEqual(reverse('wpf_thing', kwargs=dict(hierarchy='stuff/', slug='morestuff')), '/blog2/thing/stuff/morestuff/')
        self.assertEqual(reverse('wpf_thing', kwargs=dict(hierarchy='stuff/', slug='morestuff', page=2)), '/blog2/thing/stuff/morestuff/page/2/')
        # archives
        self.assertEqual(reverse('wpf_archive', kwargs=dict(year=2012, month='02')), '/blog2/2012/02/')
        self.assertEqual(reverse('wpf_archive', kwargs=dict(year=2012, month='02', page=3)), '/blog2/2012/02/page/3/')
        self.assertEqual(reverse('wpf_archive', kwargs=dict(year=2012)), '/blog2/2012/')
        self.assertEqual(reverse('wpf_archive', kwargs=dict(year=2012, page=3)), '/blog2/2012/page/3/')
        # author
        self.assertEqual(reverse('wpf_author', kwargs=dict(slug='ludo')), '/blog2/author/ludo/')
        self.assertEqual(reverse('wpf_author', kwargs=dict(slug='ludo', page=2)), '/blog2/author/ludo/page/2/')
        # search
        self.assertEqual(reverse('wpf_search'), '/blog2/search/')
        self.assertEqual(reverse('wpf_search', kwargs=dict(q='something')), '/blog2/search/something/')
        self.assertEqual(reverse('wpf_search', kwargs=dict(q='something', page=2)), '/blog2/search/something/page/2/')
        # post formats
        self.assertEqual(reverse('wpf_post_format', kwargs=dict(post_format='gallery')), '/blog2/type/gallery/')
        self.assertEqual(reverse('wpf_post_format', kwargs=dict(post_format='gallery', page=2)), '/blog2/type/gallery/page/2/')
        # posts
        self.assertEqual(reverse('wpf_post', kwargs=dict(category='stuff', id=1, slug='post-title')), '/blog2/stuff/1/post-title/')
        self.assertEqual(reverse('wpf_post', kwargs=dict(category='stuff', id=1, slug='post-title', page=2)), '/blog2/stuff/1/post-title/comment-page-2/')
        # attachments
        self.assertEqual(reverse('wpf_attachment', kwargs=dict(category='stuff', id=1, slug='post-title', attachment_slug='image-name')), '/blog2/stuff/1/post-title/attachment/image-name/')
        self.assertEqual(reverse('wpf_attachment', kwargs=dict(category='stuff', id=1, slug='post-title', attachment_slug='image-name', page=2)), '/blog2/stuff/1/post-title/attachment/image-name/comment-page-2/')
        # media
        self.assertEqual(reverse('wpf_media', kwargs=dict(filepath='2012/02/image-file.jpg')), '/blog2/files/2012/02/image-file.jpg')
