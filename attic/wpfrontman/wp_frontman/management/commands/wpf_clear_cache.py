import time

from optparse import make_option

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError

from wp_frontman.blog import Blog
from wp_frontman.cache import get_key


class Command(BaseCommand):
    
    option_list = BaseCommand.option_list + (
        make_option(
            "--clear", action="store_true", dest="clear", default=False,
            help="clear all keys from the cache"
        ),
    )
    
    def handle(self, *args, **opts):
        if opts['clear']:
            print "clearing all keys from the cache"
            cache.clear()
        else:
            print "setting the post, page, comment timestamps in the cache for all blogs"
            expiration_time = settings.CACHE_MIDDLEWARE_SECONDS
            now = time.time()
            for blog in Blog.get_blogs():
                cache.set_many(dict((
                    (get_key(blog.blog_id, 'post'), now),
                    (get_key(blog.blog_id, 'page'), now),
                    (get_key(blog.blog_id, 'comment'), now),
                    )), expiration_time
                )
