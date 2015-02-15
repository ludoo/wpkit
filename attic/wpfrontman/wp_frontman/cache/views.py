import datetime

from hashlib import sha256

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseServerError
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt

from wp_frontman.blog import Blog
from wp_frontman.cache import cache_timestamps, get_key
from wp_frontman.lib.external.phpserialize import phpobject, loads as php_unserialize


SALT = Blog.site.wp_logged_in_salt
ALLOWED_HOSTS = getattr(settings, 'WPF_CACHE_ALLOWED_HOSTS', '').split()
CACHE_TIMEOUT = settings.CACHE_MIDDLEWARE_SECONDS


if cache is None:
    raise ImproperlyConfigured("No cache found")
if not SALT:
    raise ImproperlyConfigured("Missing key or salt")


@csrf_exempt
def set_timestamp(request):
    """
    global timestamps: post, comment, page
    per-object timestamps: post-[id], comment-post-[id], category-[id] etc.
    """
    if cache is None:
        return HttpResponseBadRequest("No cache defined.")
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid HTTP method.")
    for i, payload in enumerate(request.raw_post_data.split("\n")):
        data = payload.split('|', 4)
        if len(data) != 5:
            return HttpResponseBadRequest("Incorrect format for payload %s, found %s fields." % (i, len(data)))
        blog_id, obj_type, timestamp, hash, value = data
        try:
            timestamp = int(timestamp)
        except (TypeError, ValueError):
            return HttpResponseBadRequest("Incorrect format for timestamp %s" % timestamp)
        # TODO: check if we already have a timestamp and if it's newer than this one
        _hash = sha256("%s%s%s%s%s" % (SALT, blog_id, obj_type, value, timestamp)).hexdigest()
        if hash != _hash:
            return HttpResponseForbidden(
                "Incorrect hash for blog_id %s\nobj_type %s\nvalue %s\ntimestamp %s\n_hash %s\nhash  %s" % (blog_id, obj_type, value, timestamp, _hash, hash)
            )
        obj = php_unserialize(value, object_hook=phpobject)
        try:
            cache_timestamps(blog_id, obj_type, obj, timestamp)
        except Exception, e:
            file('/tmp/wpf_cache.log', 'a+').write("%s\n" % e)
            return HttpResponseServerError("Error response from cache_timestamps: %s" % e)
    return HttpResponse('OK', content_type='text/plain')


def stats(request):
    blog = request.GET.get('blog_id')
    if blog:
        blogs = [blog]
    else:
        blogs = [b.blog_id for b in Blog.get_blogs()]
    keys = list()
    for blog_id in blogs:
        for k in ('__all__', 'taxonomy', 'post', 'page', 'comment', 'regen'):
            keys.append(get_key(blog_id, k))
    items = cache.get_many(keys)
    #if not items:
    #    return HttpResponse('OK', content_type='text/plain')
    return HttpResponse("\n".join(" ".join(k.split('.')[-2:] + [str(v)]) for k,v in items.items()), content_type='text/plain')
