from django.conf import settings
from django.template.loaders.filesystem import Loader as StockLoader
from django.utils._os import safe_join

from wp_frontman.models import Blog


class Loader(StockLoader):

    def get_template_sources(self, template_name, template_dirs=None):
        # TODO: scan the template dirs at blog instantiation, so that we can
        #       skip the first yield if there's no blog theme dir
        blog = Blog.get_active()
        key = 'wpf_site_%s_blog_%s' % (blog.site.site_id, blog.blog_id)
        if not template_dirs:
            template_dirs = settings.TEMPLATE_DIRS
        for template_dir in template_dirs:
            try:
                yield safe_join(template_dir, key, template_name)
            except UnicodeDecodeError:
                raise
            except ValueError:
                pass
            try:
                yield safe_join(template_dir, template_name)
            except UnicodeDecodeError:
                raise
            except ValueError:
                pass


_loader = Loader()


def load_template_source(template_name, template_dirs=None):
    # For backwards compatibility
    import warnings
    warnings.warn(
        "%s.load_template_source' is deprecated; use '%s.Loader' instead." % (__name__, __name__),
        DeprecationWarning
    )
    return _loader.load_template_source(template_name, template_dirs)
load_template_source.is_usable = True
