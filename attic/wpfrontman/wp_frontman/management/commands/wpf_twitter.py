# encoding: utf8

import datetime
import urllib
import urllib2
import twitter

from django.conf import settings
from django.core.urlresolvers import set_urlconf
from django.core.management.base import BaseCommand, CommandError

from wp_frontman.blog import Blog
from wp_frontman.models import Post, PostMeta
from wp_frontman.lib.logging_config import logging_config, set_logging_level


logger, log_handler = logging_config('wp_frontman.twitter')

TINYURL = 'http://tinyurl.com/api-create.php'


class Command(BaseCommand):
    
    help = "Post status updates to twitter."
    requires_model_validation = False
    
    def handle(self, *args, **opts):
        set_logging_level(logger, log_handler, opts['verbosity'])
        
        limit = datetime.datetime.now() - datetime.timedelta(days=1)
        
        for blog_id, credentials in getattr(settings, 'WPF_TWITTER', dict()).items():
            api = twitter.Api(**credentials)
            try:
                api.VerifyCredentials()
            except twitter.TwitterError, e:
                logger.critical("Authentication error for blog '%s': %s" % (blog_id, e))
            blog = Blog.factory(blog_id)
            set_urlconf(blog.urlconf)
            blog_url = blog.options['home']
            if blog_url[-1] == '/':
                blog_url = blog_url[:-1]
            for p in Post.objects.filter(status='publish', date__gt=limit).order_by('-date'):
                if p.postmeta_set.filter(name='_wpf_twitter'):
                    logger.debug("Status update for post '%s' already sent, skipping" % p.title.encode('utf-8'))
                    continue
                try:
                    link = urllib2.urlopen(
                        TINYURL,
                        data=urllib.urlencode(dict(url=blog_url + p.get_absolute_url()))
                    ).read().strip()
                except Exception, e:
                    logger.warning("Error calling tinyurl service for post '%s': %s" % (p.id, e))
                    continue
                status = "%s - %s" % (p.title.encode('utf-8'), link)
                if len(status) > 140:
                    status = status[:139] + '…'
                try:
                    api.PostUpdate(status)
                except (urllib2.HTTPError, twitter.TwitterError), e:
                    logger.warning("Error posting status '%s' for post '%s': %s" % (status, p.id, e))
                    continue
                pm = PostMeta(post=p, name='_wpf_twitter', value=True)
                pm.save()

