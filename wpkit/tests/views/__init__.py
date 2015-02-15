import os

from django.conf import settings
from django.test import TestCase

from wpkit.models import Site


blog = Site.objects.get_default().get_blog(1)


class TestView(TestCase):
    
    blog = blog
    urls = blog.urlconf
    
    @classmethod
    def setUpClass(cls):
        blog.settings_reset({
            'template_dir':os.path.join(settings.BASE_DIR, 'wpkit/tests/templates/blog_1')
        })
        
    @classmethod
    def tearDownClass(cls):
        blog.settings_reset()
    
