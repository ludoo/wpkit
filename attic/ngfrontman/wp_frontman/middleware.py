from urlparse import urlsplit

from django.conf import settings
from django.http import HttpResponseRedirect, Http404
from django.core.urlresolvers import set_urlconf

from wp_frontman.models import Blog
#from wp_frontman.views import page


DEBUG_BLOG_ID = getattr(settings, 'WPF_DEBUG_BLOG_ID', None)


class BlogMiddleware(object):
    
    def process_request(self, request):
        if DEBUG_BLOG_ID:
            blog = Blog.factory(DEBUG_BLOG_ID, active=True)
        else:
            try:
                blog_id = Blog.find_blog_id(domain=request.META['HTTP_HOST'], path=request.path)
            except ValueError, e:
                return HttpResponseRedirect("http://%s%s" % (e.args[0], request.path))
            if blog_id is None:
                raise Http404("No such domain or path.")
            try:
                blog = Blog.factory(blog_id, active=True)
            except ValueError, e:
                raise Http404(str(e))
        request.urlconf = blog.urlconf
        request.blog = blog
        
    def process_response(self, request, response):
        if hasattr(request, 'blog'):
            request.blog.cache.clear()
        return response


# TODO: port the page fallback middleware from the old code
