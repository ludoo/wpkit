import os
import logging

from urlparse import urlsplit, urlunsplit, SplitResult

from django.utils.functional import cached_property

from .utils import strtobool, php_unserialize


logger = logging.getLogger('wpkit.wp.options')


class Options(object):
    
    OPTION_PARSERS = {}
    
    def __init__(self, data):
        self._options_data = dict(data)
    
    def __getattr__(self, name):
        try:
            value = self._options_data[name]
        except KeyError:
            return
        func = getattr(type(self), '_do_%s' % name, self.OPTION_PARSERS.get(name))
        if func:
            value = func(value)
        setattr(self, name, value)
        return value
    
    def __len__(self):
        return len(self._options_data)
    
    def __contains__(self, item):
        return item in self._options_data
    
    def __iter__(self):
        for k in self._options_data:
            yield k, getattr(self, k)
    
    
class WPSiteOptions(Options):
    
    OPTION_PARSERS = {
        'admin_user_id': int,
        'registration': lambda v: v != 'none',
        'registrationnotification': lambda v: v == 'yes',
        'site_admins': php_unserialize,
        'subdomain_install': strtobool
    }
    
    def __init__(self, data):
        #logger.debug(data[0])
        super(WPSiteOptions, self).__init__((t[2:4] for t in data))


class WPBlogOptions(Options):
    
    OPTION_PARSERS = {
        'blog_public': strtobool,
        'category_children': php_unserialize,
        'comment_max_links': int,
        'comment_moderation': bool,
        'comment_registration': strtobool,
        'comment_whitelist': strtobool,
        'comments_notify': strtobool,
        'comments_per_page': int,
        'default_category': int,
        'default_link_category': int,
        'default_pingback_flag': strtobool,
        'links_recently_updated_time': int,
        'mailserver_port': int,
        'moderation_notify': strtobool,
        'page_comments': strtobool,
        'posts_per_page': int,
        'posts_per_rss': int,
        'require_name_email': strtobool,
        'rewrite_rules': php_unserialize,
        'rss_use_excerpt': bool,
        'show_avatars': strtobool,
        'start_of_week': int,
        'thread_comments': strtobool,
        'thread_comments_depth': int,
        'use_trackback': strtobool,
        'wp_user_roles': php_unserialize,
        'wp_frontman': php_unserialize,
        'wp_frontman_site': php_unserialize,
    }

    def __init__(self, data):
        super(WPBlogOptions, self).__init__((t[1:3] for t in data))

    @cached_property
    def siteurl_tokens(self):
        return urlsplit(self.siteurl)
        
    @staticmethod
    def _do_siteurl(value):
        tokens = urlsplit(value)
        if not tokens.path:
            tokens = SplitResult(
                tokens.scheme, tokens.netloc, '/', tokens.query, tokens.fragment
            )
        return urlunsplit(tokens)
        
        
class WPPostMeta(Options):
    
    @staticmethod
    def _do_wp_attachment_metadata(value):
        value = php_unserialize(value)
        if value['file']:
            base = os.path.dirname(value['url'])
            if isinstance(value.get('sizes'), dict):
                for k, v in value['sizes'].items():
                    if 'file' in v:
                        v['url'] = base + '/' + v['file']
        return value
