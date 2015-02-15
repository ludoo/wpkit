import time
import datetime

from hashlib import sha256

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt

from wp_frontman.models import Blog
from wp_frontman.lib.external.phpserialize import loads as unserialize, phpobject


CACHE_KEY_PREFIX = settings.CACHE_MIDDLEWARE_KEY_PREFIX
CACHE_KEY_PREFIX = '' if not CACHE_KEY_PREFIX else '.%s' % CACHE_KEY_PREFIX
ALLOWED_HOSTS = getattr(settings, 'WPF_CACHE_ALLOWED_HOSTS', '').split()
CACHE_TIMEOUT = settings.CACHE_MIDDLEWARE_SECONDS


class PayloadError(Exception): pass


def _verify_request(request):
    if cache is None:
        raise PayloadError("No Django cache set", HttpResponseServerError)
    if request.method != 'POST':
        raise PayloadError("Invalid HTTP method.", HttpResponseBadRequest)
    for i, payload in enumerate(request.raw_post_data.split("\n")):
        data = payload.split('|', 6)
        if len(data) != 6:
            raise PayloadError("Incorrect format for payload %s, found %s fields." % (i, len(data)), HttpResponseBadRequest)
        yield data
        

def _unpack_payload(site_id, blog_id, obj_type, timestamp, hash, value):
    try:
        site_id = int(site_id)
        blog_id = int(blog_id)
    except (TypeError, ValueError):
        raise PayloadError("Invalid site or blog id.", HttpResponseBadRequest)
    blog = Blog.factory(blog_id)
    site = blog.site
    # TODO: initialize the proper site so that we can support a global cache application
    if site.site_id != site_id:
        raise PayloadError("Incorrect site id %s instead of %s." % (site.site_id, site_id), HttpResponseBadRequest)
    salt = site.meta['wp_frontman'].get('wp_logged_in_salt')
    if not salt:
        raise PayloadError("No salt for site id %s." % site_id, HttpResponseServerError)
    try:
        timestamp = int(timestamp)
    except (TypeError, ValueError):
        raise PayloadError("Incorrect format for timestamp %s" % timestamp, HttpResponseBadRequest)
    # TODO: check if we already have a timestamp and if it's newer than this one
    _hash = sha256("%s%s%s%s%s%s" % (salt, site_id, blog_id, obj_type, value, timestamp)).hexdigest()
    if hash != _hash:
        raise PayloadError(
            "Incorrect hash for site_id %s blog_id %s\nobj_type %s\nvalue %s\ntimestamp %s\n_hash %s\nhash  %s" % (
            site_id, blog_id, obj_type, value, timestamp, _hash, hash
        ), HttpResponseForbidden)
    t = time.time()
    if timestamp >= t:
        raise PayloadError("Future timestamp.", HttpResponseBadRequest)
    if timestamp < t - 300:
        raise PayloadError("Timestamp expired.", HttpResponseBadRequest)
    obj = unserialize(value, object_hook=phpobject)
    return site_id, blog_id, obj_type, value, timestamp


@csrf_exempt
def ping(request):
    try:
        payloads = [_unpack_payload(*p) for p in _verify_request(request)]
    except PayloadError, e:
        message, response = e.args
        return response(message)
    if len(payloads) > 1:
        return HttpResponseBadRequest("Expected 1 payload, received %s." % len(payloads))
    site_id, blog_id, obj_type, value, timestamp = payloads[0]
    if obj_type != 'ping':
        return HttpResponseBadRequest("Unknown payload type '%s'." % obj_type)
    return HttpResponse('PONG sent at %s' % datetime.datetime.now().isoformat(), content_type='text/plain')


@csrf_exempt
def query(request):
    try:
        payloads = [_unpack_payload(*p) for p in _verify_request(request)]
    except PayloadError, e:
        message, response = e.args
        return response(message)
    if len(payloads) > 1:
        return HttpResponseBadRequest("Expected 1 payload, received %s." % len(payloads))
    site_id, blog_id, obj_type, value, timestamp = payloads[0]
    if obj_type != 'query':
        return HttpResponseBadRequest("Unknown payload type '%s'." % obj_type)
    return HttpResponse('query command not implemented yet', content_type='text/plain')
