from django.conf import settings
from django.template.loaders.filesystem import Loader
from django.utils._os import safe_join

from wp_frontman.blog import Blog


class WPFLoader(Loader):

    def get_template_sources(self, template_name, template_dirs=None):
        """
        Returns the absolute paths to "template_name", when appended to each
        directory in "template_dirs". Any paths that don't lie inside one of the
        template dirs are excluded from the result set, for security reasons.
        """
        # TODO: scan the template dirs at blog instantiation, so that we can
        #       skip the first yield if there's no blog theme dir
        blog_id = 'blog_%s' % Blog.get_active().blog_id
        if not template_dirs:
            template_dirs = settings.TEMPLATE_DIRS
        for template_dir in template_dirs:
            try:
                yield safe_join(template_dir, blog_id, template_name)
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


_loader = WPFLoader()


def load_template_source(template_name, template_dirs=None):
    # For backwards compatibility
    import warnings
    warnings.warn(
        "'django.template.loaders.filesystem.load_template_source' is deprecated; use 'django.template.loaders.filesystem.Loader' instead.",
        PendingDeprecationWarning
    )
    return _loader.load_template_source(template_name, template_dirs)
load_template_source.is_usable = True
