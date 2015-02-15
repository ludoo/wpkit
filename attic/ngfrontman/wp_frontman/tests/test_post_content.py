import unittest

from difflib import unified_diff

from django.db import connections

from wp_frontman.models import Site, Blog
from wp_frontman.tests.utils import MultiBlogMixin


GALLERY_CONTENT = u'<p>Post with attachments.</p>\n\n\t\t<style type=\'text/css\'>\n\t\t\t#gallery-1 {\n\t\t\t\tmargin: auto;\n\t\t\t}\n\t\t\t#gallery-1 .gallery-item {\n\t\t\t\tfloat: left;\n\t\t\t\tmargin-top: 10px;\n\t\t\t\ttext-align: center;\n\t\t\t\twidth: 33%;\n\t\t\t}\n\t\t\t#gallery-1 img {\n\t\t\t\tborder: 2px solid #cfcfcf;\n\t\t\t}\n\t\t\t#gallery-1 .gallery-caption {\n\t\t\t\tmargin-left: 0;\n\t\t\t}\n\t\t</style>\n\t\t<!-- see gallery_shortcode() in wp-includes/media.php -->\n\t\t<div id=\'gallery-1\' class=\'gallery galleryid-0 gallery-columns-3 gallery-size-thumbnail\'><dl class=\'gallery-item\'>\n\t\t\t<dt class=\'gallery-icon\'>\n\t\t\t\t<a href=\'/2012/02/attachment-test/walias-band/\' title=\'walias band\'><img width="150" height="150" src="/wp-content/uploads/2012/02/walias-band-150x150.jpg" class="attachment-thumbnail" alt="walias band" /></a>\n\t\t\t</dt></dl><dl class=\'gallery-item\'>\n\t\t\t<dt class=\'gallery-icon\'>\n\t\t\t\t<a href=\'/2012/02/attachment-test/the-best-of-walias/\' title=\'The Best of Walias\'><img width="150" height="150" src="/wp-content/uploads/2012/02/The-Best-of-Walias-150x150.jpg" class="attachment-thumbnail" alt="The Best of Walias" /></a>\n\t\t\t</dt></dl>\n\t\t\t<br style=\'clear: both;\' />\n\t\t</div>\n\n'
POST_CONTENT = u'<p>This is an example page modified. It&#8217;s different from a blog post because it will stay in one place and will show up in your site navigation (in most themes). Most people start with an About page that introduces them to potential site visitors. It might say something like this:</p>\n<blockquote><p>Hi there! I&#8217;m a bike messenger by day, aspiring actor by night, and this is my blog. I live in Los Angeles, have a great dog named Jack, and I like pi\xf1a coladas. (And gettin&#8217; caught in the rain.)</p></blockquote>\n<p>&#8230;or something like this:<span id="more-1"></span></p>\n<blockquote><p>The XYZ Doohickey Company was founded in 1971, and has been providing quality doohickies to the public ever since. Located in Gotham City, XYZ employs over 2,000 people and does all kinds of awesome things for the Gotham community.</p></blockquote>\n<p>As a new WordPress user, you should go to <a href="/wp-admin/">your dashboard</a> to delete this page and create new pages for your content. Have fun!</p>\n'
POST_SUMMARY = u'<p>This is an example page modified. It&#8217;s different from a blog post because it will stay in one place and will show up in your site navigation (in most themes). Most people start with an About page that introduces them to potential site visitors. It might say something like this:</p>\n<blockquote><p>Hi there! I&#8217;m a bike messenger by day, aspiring actor by night, and this is my blog. I live in Los Angeles, have a great dog named Jack, and I like pi\xf1a coladas. (And gettin&#8217; caught in the rain.)</p></blockquote>\n<p>&#8230;or something like this:</p>\n'
POST_EXCERPT = u'This is an example page modified. It&#8217;s different from a blog post because it will stay in one place and will show up in your site navigation (in most themes). Most people start with an About page that introduces them to potential site visitors. It'


class Differ(object):
    
    def __init__(self, expected, result):
        self.expected = expected if isinstance(expected, str) else expected.encode('utf-8')
        self.result = result if isinstance(result, str) else result.encode('utf-8')
        
    def __str__(self):
        diff = list(unified_diff(
            self.expected.split("\n"), self.result.split("\n"), 'original', 'result'
        ))
        if diff:
            return "\n" + "\n".join(diff)
        return '[--- no differences found ---]'
        

class PostContentTestCase(MultiBlogMixin, unittest.TestCase):

    def setUp(self):
        super(PostContentTestCase, self).setUp()
        self.cursor = connections['test'].cursor()
        self.cursor_mu = connections['test_multi'].cursor()
        
    def testPreformattedGallery(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        post = blog.models.BasePost.objects.get(id=13)
        self.assertTrue(post.more is False and post.summary_parsed == post.content_parsed and post.summary == post.content)
        self.assertTrue(post.content != post.content_parsed)
        self.assertEqual(post.content_parsed, GALLERY_CONTENT, Differ(GALLERY_CONTENT, post.content_parsed))
        self.assertEqual(post.excerpt, u'Post with attachments.')
        
    def testPreformattedMore(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        post = blog.models.BasePost.objects.get(id=1)
        self.assertTrue(post.more is True)
        self.assertTrue(post.summary_parsed != post.content_parsed)
        self.assertTrue(post.summary != post.content)
        self.assertTrue(post.content != post.content_parsed)
        self.assertEqual(post.content_parsed, POST_CONTENT, Differ(POST_CONTENT, post.content_parsed))
        self.assertEqual(post.summary_parsed, POST_SUMMARY)
        self.assertEqual(post.excerpt, POST_EXCERPT)
        
    def testGalleryImages(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        post = blog.models.BasePost.objects.get(id=13)
        self.assertEqual([p.id for p in post.gallery_images], [102,101])
        
    def testFeaturedImage(self):
        self.reset_blog_class(mu=False)
        blog = Blog(1)
        post = blog.models.BasePost.objects.get(id=13)
        featured_image = post.featured_image
        self.assertTrue(featured_image)
        self.assertEqual(post.featured_image.metadict['attached_file'], '/wp-content/uploads/2012/02/Polaroid_Land_Camera_100_IMGP1930_WP.jpg')
        
        
