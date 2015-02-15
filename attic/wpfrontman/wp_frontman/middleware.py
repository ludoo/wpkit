from urlparse import urlsplit

from django.conf import settings
from django.http import HttpResponseRedirect, Http404
from django.core.urlresolvers import set_urlconf

from wp_frontman.blog import Blog
from wp_frontman.views import page


OPTIONS_MODULE = getattr(settings, 'WPF_OPTIONS_MODULE', 'wpf_blogs')
DEBUG_BLOG_ID = getattr(settings, 'WPF_DEBUG_BLOG_ID', None)


class WPFBlogMiddleware(object):
    
    def process_request(self, request):
        if DEBUG_BLOG_ID:
            blog = Blog.factory(DEBUG_BLOG_ID)
        elif Blog.site.subdomain_install:
            try:
                blog = Blog.site.blog_for_domain(request.META['HTTP_HOST'])
            except ValueError, e:
                return HttpResponseRedirect("http://%s%s" % (e.args[0], request.path))
        else:
            blog = Blog.site.blog_for_path(request.path)
        request.urlconf = blog.urlconf
        request.blog = blog
        
    def process_response(self, request, response):
        if hasattr(request, 'blog'):
            request.blog.cache.clear()
        return response


class WPFrontmanPageFallbackMiddleware(object):
    
    def process_response(self, request, response):
        if response.status_code != 404:
            return response # No need to check for a flatpage for non-404 responses.
        if request.path in ('/favicon.ico', '/robots.txt'):
            # shortcircuit common missing files
            return response
        tokens = [t for t in urlsplit(request.path).path.split('/') if t]
        l = len(tokens)
        if l == 0:
            return response
        comment_page = None
        blog = Blog.get_active()
        if not blog.thread_comments:
            if l > 1:
                return response
        else:
            if l > 2:
                return response
            if l == 2:
                if not tokens[1].startswith('comment-page-'):
                    return response
                try:
                    comment_page = int(tokens[1][13:])
                except (TypeError, ValueError):
                    return response
        slug = tokens[0]
        set_urlconf(blog.urlconf)
        try:
            return page(request=request, slug=slug, comment_page=comment_page)
        except Http404:
            return response
        except:
            if settings.DEBUG:
                raise
            return response
        finally:
            set_urlconf(None)
