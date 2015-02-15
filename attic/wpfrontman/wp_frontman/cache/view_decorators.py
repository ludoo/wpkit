import time
import datetime

from types import FunctionType

from django.conf import settings
from django.core.cache import cache
from django.middleware.cache import UpdateCacheMiddleware
from django.utils.cache import get_cache_key, get_max_age, patch_response_headers, learn_cache_key

from wp_frontman.blog import Blog
from wp_frontman.cache import get_key


CACHE_DEBUG = getattr(settings, 'CACHE_DEBUG', False)


class WPFCache(UpdateCacheMiddleware):
    
    def __init__(self, cache_timeout=None, key_prefix=None, timestamps=None):
        self.cache_timeout = cache_timeout or getattr(settings, 'CACHE_MIDDLEWARE_SECONDS')
        self.key_prefix = key_prefix or getattr(settings, 'CACHE_MIDDLEWARE_KEY_PREFIX')
        self.timestamps = timestamps or ('__all__',)
    
    def get_key_prefix(self, blog_id):
        key_prefix = 'blog_%s' % blog_id
        if self.key_prefix:
            key_prefix = '%s.%s' % (self.key_prefix, key_prefix)
        return key_prefix
        
    def wrap(self, view_func):
        self.view_func = view_func
        return self.run_view

    def _check_cache(self, blog_id, request):
        if not request.method in ('GET', 'HEAD') or request.GET or not getattr(request, '_cache_store_result', True):
            request._cache_store_result = False
            return
        key = get_cache_key(request, self.get_key_prefix(blog_id))
        if key is None:
            request._cache_store_result = True
            return
        # TODO: use a single get_many call for both values and timestamps
        value = cache.get(key, None)
        if value is None:
            request._cache_store_result = True
            return
        try:
            timestamp, value = value
        except (TypeError, ValueError):
            request._cache_store_result = True
            return
        if timestamp:
            wp_timestamps = [int(t) for t in cache.get_many([get_key(blog_id, t) for t in self.timestamps]).values()]
            timestamp = int(timestamp)
            if wp_timestamps and timestamp <= max(wp_timestamps):
                request._cache_store_result = True
                return
        if CACHE_DEBUG:
            value.content += '\n<!-- served on %s -->' % datetime.datetime.now()
        return value
    
    def run_view(self, request, *args, **kw):
        blog_id = Blog.get_active().blog_id
        response = self._check_cache(blog_id, request)
        if response:
            return response
        response = self.view_func(request, *args, **kw)
        if response.status_code != 200 or not getattr(request, '_cache_store_result', True):
            return response
        timeout = get_max_age(response)
        if timeout == 0:
            return response
        timeout = timeout or self.cache_timeout
        patch_response_headers(response, timeout)
        if timeout:
            if CACHE_DEBUG:
                response.content = response.content + ('\n<!--\nend %s\ncached on %s\n-->' % (self.view_func.func_name, datetime.datetime.now()))
            cache_key = learn_cache_key(request, response, timeout, self.get_key_prefix(blog_id))
            cache.set(cache_key, (time.time(), response), timeout)
        return response
    

def wpf_cache_page(cache_timeout=None, timestamps=None, key_prefix=None):
    if timestamps is None and key_prefix is None and isinstance(cache_timeout, FunctionType):
        decorator = WPFCache()
        return decorator.wrap(cache_timeout)
    decorator = WPFCache(cache_timeout, key_prefix, timestamps)
    return decorator.wrap
