"""
Wrapper class that takes a list of template loaders as an argument and attempts
to load templates from them in order, caching the result.

Basically identical to the django default caching loader, but takes
into account the blog id.
"""

from django.template.loaders.cached import Loader as BaseLoader

from wp_frontman.models import Blog


class Loader(BaseLoader):

    def load_template(self, template_name, template_dirs=None):
        
        blog = Blog.get_active()
        key = '%s-%s-%s' % (site.site_id, blog.blog_id, template_name)
        
        if template_dirs:
            # If template directories were specified, use a hash to differentiate
            key = '-'.join([siste.site_id, blog.blog_id, template_name, sha_constructor('|'.join(template_dirs)).hexdigest()])

        if key not in self.template_cache:
            template, origin = self.find_template(template_name, template_dirs)
            if not hasattr(template, 'render'):
                try:
                    template = get_template_from_string(template, origin, template_name)
                except TemplateDoesNotExist:
                    # If compiling the template we found raises TemplateDoesNotExist,
                    # back off to returning the source and display name for the template
                    # we were asked to load. This allows for correct identification (later)
                    # of the actual template that does not exist.
                    return template, origin
            self.template_cache[key] = template
        return self.template_cache[key], None

