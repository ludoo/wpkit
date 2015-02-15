import time
import datetime

from hashlib import md5

from django.conf import settings
from django.core.cache import cache


CACHE_KEY_PREFIX = settings.CACHE_MIDDLEWARE_KEY_PREFIX
CACHE_KEY_PREFIX = '' if not CACHE_KEY_PREFIX else '.%s' % CACHE_KEY_PREFIX
CACHE_DEBUG = getattr(settings, 'CACHE_DEBUG', False)


def get_key(blog_id, key_type, obj_id=None):
    if not obj_id:
        return 'wpf.cache.timestamp%s.blog.%s.%s' % (CACHE_KEY_PREFIX, blog_id, key_type)
    return 'wpf.cache.timestamp%s.blog.%s.%s.%s' % (CACHE_KEY_PREFIX, blog_id, key_type, obj_id)


def get_object_key(blog_id, obj_type, obj_attrs):
    return 'wpf.cache.objects.blog.%s.%s.%s' % (blog_id, obj_type, md5(repr(obj_attrs)).hexdigest())


def get_object_value(blog_id, key, obj_types):
    obj = cache.get(key)
    if not obj:
        return
    obj_timestamp, obj = obj
    timestamps_keys = [get_key(blog_id, t, obj.id) for t in obj_types]
    timestamps = cache.get_many(timestamps_keys)
    if CACHE_DEBUG:
        file('/tmp/wpf_cache.log', 'a+').write("get_object_value key %s obj %s\n--- obj_timestamp %s\n--- timestamps keys %s\n--- timestamps %s\n" % (key, obj, obj_timestamp, timestamps_keys, timestamps))
    if not timestamps or max(timestamps.values()) < obj_timestamp:
        return obj

        
def set_object_value(key, obj):
    cache.set(key, (time.time(), obj))
    

def cache_timestamps(blog_id, obj_type, obj, timestamp):
    to_cache = dict()
    to_cache[get_key(blog_id, '__all__')] = timestamp
    to_cache[get_key(blog_id, obj_type)] = timestamp
    if obj_type in ('post', 'page'):
        to_cache[get_key(blog_id, obj_type, obj['id'])] = timestamp
        #to_cache[get_key(blog_id, '%s_path' % key, obj['path'])] = timestamp
        to_cache[get_key(blog_id, 'author', obj['author_id'])] = timestamp
        #to_cache[get_key(blog_id, 'author_nicename', obj['author_nicename'])] = timestamp
        if obj['taxonomy']:
            # TODO: use proper taxonomy names, eg category, post_tag, etc.
            to_cache[get_key(blog_id, 'taxonomy')] = timestamp
            for t in obj['taxonomy'].values():
                to_cache[get_key(blog_id, t['taxonomy'], t['id'])] = timestamp
                #to_cache[get_key(blog_id, t['taxonomy'] + '_path', t['path'])] = timestamp
        # archive 2007-10-05 16:01:49
        try:
            date = datetime.datetime.strptime(obj['date'], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass
        else:
            to_cache[get_key(blog_id, 'archive', date.strftime('%Y'))] = timestamp
            to_cache[get_key(blog_id, 'archive', date.strftime('%Y%m'))] = timestamp
    elif obj_type == 'comment':
        #to_cache[get_key(blog_id, 'comment_id', obj['id'])] = timestamp
        to_cache[get_key(blog_id, 'comment_post', obj['post_id'])] = timestamp
        #to_cache[get_key(blog_id, 'comment_post_path', obj['path'])] = timestamp
    elif obj_type == 'regen':
        # set the global timestamp
        to_cache[get_key(blog_id, 'taxonomy')] = timestamp
    if CACHE_DEBUG:
        file('/tmp/wpf_cache.log', 'a+').write("setting timestamps\n--- %s\n" % "\n--- ".join("%s = %s" % t for t in to_cache.items()))
    if to_cache:
        res = cache.set_many(to_cache)
    