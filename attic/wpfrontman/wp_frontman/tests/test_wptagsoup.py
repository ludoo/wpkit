import unittest
import re

from wp_frontman.blog import Blog
from wp_frontman.models import Post
from wp_frontman.lib.wp_tagsoup import convert


space_stripper = re.compile(r'\n+', re.M|re.S)


class WPTagSoupTestCase(unittest.TestCase):

    def setUp(self):
        Blog.default_active()
    
    def testPostContent(self):
        for p in Post.objects.published():
            converted_summary = space_stripper.sub(' ', convert(p.summary).strip())
            wp_summary = space_stripper.sub(' ', p.summary_parsed.strip())
            self.assertEqual(converted_summary, wp_summary, p.id)
            converted_content = space_stripper.sub(' ', convert(p.content).strip())
            converted_content = p._more_re.sub('<span id="more-%s"></span>' % p.id, converted_content)
            wp_content = space_stripper.sub(' ', p.content_parsed.strip())
            self.assertEqual(converted_content, wp_content, p.id)
            
    def testContent(self):
        content = u'<p class="image_container"><img class="frame_left" title="Samyang 8mm f/3.5 fisheye" src="http://altroformato.it/files/2011/08/samyang_8mm_small.jpg" alt="Samyang 8mm f/3.5 fisheye" width="278" height="278" />\r\n<span class="image_attribution">image by Janne@<a href="http://www.flickr.com/photos/jannefoo/4442053170/">Flickr</a></span></p>\r\nPhotozone ha appena rilasciato una<a href="http://www.photozone.de/sony-alpha-aps-c-lens-tests/665-samyang8f35nex"> prova del fisheye Samyang 8mm f/3.5\xa0CS VG10</a> -- venduto per la videocamera NEX VG10 ma perfettamente usabile su qualsiasi corpo NEX -- accoppiato a una Sony NEX-5. Vediamo se anche <a href="http://www.syopt.co.kr/">questo obiettivo</a> conferma le qualit\xe0 delle altre ottiche Samyang, che grazie alla semplicit\xe0 costruttiva resa possibile dalla messa a fuoco manuale offrono una ottima resa ad un prezzo davvero contenuto (250\u20ac per un buon fisheye non sono molti).\r\n\r\nAaaa<!--more-->'
        converted_content = convert(content)
        
