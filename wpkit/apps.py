from threading import local

from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings

from .wp.config import parse_config


class WpKitConfig(AppConfig):
    name = 'wpkit'
    verbose_name = "WpKit WP Frontend"
    
    def __init__(self, *args, **kw):
        super(WpKitConfig, self).__init__(*args, **kw)
        try:
            self.wp_root = settings.WPKIT_WP_ROOT
        except AttributeError:
            raise ImproperlyConfigured("No WPKIT_WP_ROOT configuration value found in settings")
        if self.wp_root.endswith('/'):
            self.wp_root = self.wp_root[:-1]
        try:
            self.wp_config = parse_config(self.wp_root)
        except ValueError, e:
            raise ImproperlyConfigured("Error parsing WP config: %s" % e)
        self._site = None
        self._app_globals = local()
        
    @property
    def site(self):
        return self._site
    
    @site.setter
    def site(self, site):
        self._site = site
    
    @property
    def blog(self):
        return getattr(self._app_globals, 'blog', None)

    @blog.setter
    def blog(self, blog):
        self._app_globals.blog = blog
