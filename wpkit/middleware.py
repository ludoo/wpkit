import logging

from django.apps import apps
from django.conf import settings
from django.http import HttpResponseRedirect, Http404
from django.core.urlresolvers import set_urlconf

from .models import Site, SUBDOMAIN_INSTALL


DEBUG_BLOG_ID = getattr(settings, 'WPKIT_DEBUG_BLOG_ID', None)
REMOVE_BLOG_FROM_PATH = getattr(settings, 'WPKIT_REMOVE_BLOG_FROM_PATH', False)

app = apps.get_app_config('wpkit')
logger = logging.getLogger('wpkit.middleware')


class WpKitBlogRoutingMiddleware(object):
    
    def __init__(self):
        
        self._site = app.site = Site.objects.get_default()
        self._map = {}
        
        for blog in self._site.blogs:
            
            if SUBDOMAIN_INSTALL:
                
                domains = [blog.domain]
                if hasattr(blog, 'domainmapping_set'):
                    for dm in blog.domainmapping_set.all():
                        if dm.active:
                            domains.insert(0, dm.domain)
                        else:
                            domains.append(dm.domain)
                domain = domains.pop(0)
                self._map[domain] = blog.id
                for d in domains:
                    self._map[d] = domain
                    
            else:
                
                if REMOVE_BLOG_FROM_PATH:
                    self._map[blog.path] = blog.id
                else:
                    self._map['blog/%s' % blog.path] = blog.id
    
    def process_request(self, request):
        
        logger.debug((
            settings.DEBUG, DEBUG_BLOG_ID, request.META['HTTP_HOST'], request.path
        ))
        
        if settings.DEBUG and DEBUG_BLOG_ID:
            blog_id = DEBUG_BLOG_ID
            #request.blog = app.blog = self.site.get_blog(id=DEBUG_BLOG_ID)
        
        elif SUBDOMAIN_INSTALL:
            blog_id = self._map.get(request.META['HTTP_HOST'])
            if isinstance(blog_id, basestring):
                return HttpResponseRedirect("http://%s%s" % (blog_id, request.path))

        else:
            path_tokens = [t for t in request.path.split('/') if t]
            blog_id = self._map.get(
                path_tokens[0] if REMOVE_BLOG_FROM_PATH else '/'.join(path_tokens[:2])
            )

        if blog_id is None:
            raise Http404("No such blog")
            
        try:
            request.blog = app.blog = self._site.get_blog(blog_id)
        except models.Blog.DoesNotExist:
            # allow a global urlconf to work on a non WP managed domain
            return
            # or raise 404?
            raise Http404("No blog found")
                
        request.urlconf = request.blog.urlconf
        set_urlconf(request.urlconf)
        
        logger.debug(request.blog)


    def process_response(self, request, response):
        # unset our urlconf if we set one when processing the request
        if hasattr(request, 'blog'):
            set_urlconf(None)
        return response
        
        