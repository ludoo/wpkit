import time

from hashlib import md5

from django.conf import settings
from django import template

from django.core.cache import cache

from wp_frontman.blog import Blog
from wp_frontman.cache import get_key


CACHE_TIMEOUT = settings.CACHE_MIDDLEWARE_SECONDS
register = template.Library()


class WpfCacheNode(template.Node):
    
    def __init__(self, nodelist, block_name, obj_type, obj_id=None, *args):
        self.nodelist = nodelist
        self.block_name = template.Variable(block_name)
        self.obj_type = template.Variable(obj_type)
        self.obj_id = None if not obj_id else template.Variable(obj_id)
        self.args = [template.Variable(a) for a in args]

    def render(self, context):
        block_name = self.block_name.resolve(context)
        obj_type = self.obj_type.resolve(context)
        if self.obj_id:
            try:
                obj_id = self.obj_id.resolve(context) #int(self.obj_id.resolve(context))
            except template.VariableDoesNotExist:
                raise template.TemplateSyntaxError('"wpfcache" tag got an unknown variable: %r' % self.obj_id.var)
            except (ValueError, TypeError):
                raise template.TemplateSyntaxError('"wpfcache" tag got a non-integer object id value: %r' % self.obj_id.resolve(context))
            timestamp_key = get_key(Blog.get_active().blog_id, obj_type, obj_id)
        else:
            timestamp_key = get_key(Blog.get_active().blog_id, obj_type)
        if block_name:
            value_key =  get_key(Blog.get_active().blog_id, block_name)
        else:
            value_key =  timestamp_key + '.cached_block'
        if self.args:
            vary_args = list()
            for arg in self.args:
                try:
                    vary_args.append(arg.resolve(context))
                except template.VariableDoesNotExist:
                    vary_args.append(None)
            vary_args = ''.join(str(a) if not isinstance(a, unicode) else a.encode('utf-8') for a in vary_args)
            value_key += '.' + md5(vary_args).hexdigest()
        #request = context.get('request')
        #skip = request and (request.method != 'GET' or request.GET)
        #if not skip:
        values = cache.get_many((timestamp_key, value_key))
        timestamp = values.get(timestamp_key)
        if timestamp:
            timestamp = int(timestamp)
        value = values.get(value_key)
        if value:
            block_timestamp, value = value
            block_timestamp = int(block_timestamp)
            if not timestamp or block_timestamp > timestamp:
                return value + "\n<!-- %s served on %s -->" % (value_key, time.time())
        value = self.nodelist.render(context)
        #if skip:
        #    return value
        now = time.time()
        value = "\n<!-- %s cached on %s -->\n" % (value_key, now) + value
        cache.set(value_key, (now, value), CACHE_TIMEOUT)
        return value


def wpf_cache(parser, token):
    """
    This will cache the contents of a template fragment for a given amount
    of time.

    Usage::

        {% load wpf_cache %}
        {% wpfcache [block_name] [obj_type] [obj_id] [arg_1, ..., arg_n] %}
            .. some expensive processing ..
        {% endwpfcache %}

    """
    nodelist = parser.parse(('endwpfcache',))
    parser.delete_first_token()
    tokens = token.contents.split()
    tag = tokens.pop(0)
    if len(tokens) < 2:
        raise template.TemplateSyntaxError(u"'wpfcache' tag requires at least 2 arguments")
    return WpfCacheNode(nodelist, *tokens)


register.tag('wpfcache', wpf_cache)
