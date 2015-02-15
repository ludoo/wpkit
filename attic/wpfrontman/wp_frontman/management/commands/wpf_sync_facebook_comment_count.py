import datetime
import simplejson
import logging

from optparse import make_option
from urlparse import urljoin
from urllib import quote_plus

from django.core.urlresolvers import set_urlconf

from wp_frontman.models import Blog, BasePost
from wp_frontman.lib.command_base import CommandBase, CommandError, transaction
from wp_frontman.lib.pycurl_multi import HTTPMultiError, RequestError, HTTPRequest, HTTPClient, PROXYTYPE_HTTP, PROXYTYPE_SOCKS4, PROXYTYPE_SOCKS5


class Command(CommandBase):
    option_list = CommandBase.option_list + (
        make_option(
            "--days", type="int", dest="days", default=7,
            help="Number of days to check in the past, defaults to 7"
        ),
    )
    help = "Sync facebook comments."
    
    def _dequeue(self):
        while self.queue:
            request = self.queue.pop()
            self.logger.info("scheduling request for blog id %s post id %s" % (request.blog_id, request.post_id))
            try:
                self.client.fetch(request)
            except HTTPMultiError, e:
                self.log_message("Error adding HTTP request: %s" % e, logging.CRITICAL)
                self.handle_ok = False
                continue
            else:
                break
        
    def _process_response(self, request, response):
        #self.client._callback(request, response)
        self.logger.info("processing response for blog id %s post id %s" % (request.blog_id, request.post_id))
        if response.code == 400:
            self.log_message("HTTP 400, exiting: %s" % response.body, logging.CRITICAL)
            self.queue = []
            self.client.stop()
            raise SystemExit(1)
        if response.errno or response.errmsg:
            self.log_message("Response error for blog id %s post id %s: %s %s" % (request.blog_id, request.post_id, response.errno, response.errmsg), logging.WARN)
            self.handle_ok = False
        elif response.code != 200:
            self.log_message("HTTP status %s for blog id %s post id %s: %s" % (response.code, request.blog_id, request.post_id, response.body), logging.WARN)
            self.handle_ok = False
        else:
            try:
                data = simplejson.loads(response.body)
            except simplejson.JSONDecodeError, e:
                self.log_message("Error decoding JSON for blog id %s post id %s: %s" % (response.code, request.blog_id, request.post_id, e), logging.WARN)
                self.handle_ok = False
            else:
                if data is False:
                    self.log_message("Error in response for blog id %s post id %s: %s" % (response.code, request.blog_id, request.post_id, data))
                else:
                    comments = data.get('comments', 0)
                    self.log_message("Setting comment_count for blog id %s post id %s to %s" % (request.blog_id, request.post_id, comments))
                    self.cursor.execute(
                        "update wp_%s_posts set comment_count=%%s where id=%%s" % request.blog_id, (comments, request.post_id)
                    )
                    transaction.commit()
        self._dequeue()
            
    def _handle(self, *args, **opts):

        if not args[1:]:
            raise CommandError("No blogs to check")

        self.queue = []
            
        for blog_id in args[1:]:
            blog = Blog.factory(int(blog_id))
            set_urlconf(blog.urlconf)
            for post in BasePost.objects.filter(status='publish', post_type__in=('post', 'page'), date__gte=self.now - datetime.timedelta(days=opts['days'])):
                request = HTTPRequest("https://graph.facebook.com/%s" % quote_plus(urljoin(blog.home, post.get_absolute_url())))
                request.blog_id = blog.blog_id
                request.post_id = post.id
                self.queue.append(request)
        
        self.log_message("%s requests in queue" % len(self.queue))
        
        self.client = HTTPClient(self._process_response, 5, reuse=True, logger=self.logger)
        
        while self.client.pending < 5 and self.queue:
            try:
                self._dequeue()
            except HTTPMultiError, e:
                self.log_message("Error adding HTTP request: %s" % e, logging.CRITICAL)

        self.logger.info("starting client")
        self.client.start()
        
        
        transaction.commit()
