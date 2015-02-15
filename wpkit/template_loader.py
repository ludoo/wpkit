from django.apps import apps
from django.conf import settings
from django.template.loaders.filesystem import Loader as FileSystemLoader


app = apps.get_app_config('wpkit')


class Loader(FileSystemLoader):
    
    def get_template_sources(self, template_name, template_dirs=None):
        blog = app.blog
        if blog and 'template_dir' in blog.settings:
            template_dirs = template_dirs or settings.TEMPLATE_DIRS
            blog_dir = blog.settings['template_dir']
            if blog_dir:
                template_dirs = (blog_dir,) + tuple(d for d in template_dirs)
        return super(Loader, self).get_template_sources(template_name, template_dirs)

