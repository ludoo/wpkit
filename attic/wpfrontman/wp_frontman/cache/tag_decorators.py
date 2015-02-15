import os
import time
import datetime

from hashlib import md5
from inspect import getargspec

from django.conf import settings
from django.template import Library, Node, Variable, TemplateSyntaxError, generic_tag_compiler, VariableDoesNotExist
from django.template.context import Context
from django.core.cache import cache
from django.utils.functional import curry

from wp_frontman.blog import Blog
from wp_frontman.cache import get_key


KEY_PREFIX = getattr(settings, 'CACHE_MIDDLEWARE_KEY_PREFIX', '')
CACHE_TIMEOUT = getattr(settings, 'CACHE_MIDDLEWARE_SECONDS')
CACHE_DEBUG = getattr(settings, 'CACHE_DEBUG', False)


def cached_inclusion_tag(register, file_name, context_class=Context, takes_context=False, expire_timestamps=None, localize_template_by=None):
    
    def dec(func):
        
        params, xx, xxx, defaults = getargspec(func)
        
        cache_key_prefix = "views.decorators.cache.cache_tag%s.%s.%s" % (
            '' if not KEY_PREFIX else '.'+KEY_PREFIX,
            '.'.join(func.__module__.split('.')[-2:]),
            func.func_name
        )
            
        if takes_context:
            if params[0] == 'context':
                params = params[1:]
            else:
                raise TemplateSyntaxError("Any tag function decorated with takes_context=True must have a first argument of 'context'")

        class InclusionNode(Node):
            
            def __init__(self, vars_to_resolve):
                self.vars_to_resolve = map(Variable, vars_to_resolve)
                self._nodelists = dict()

            def render(self, context):
                resolved_vars = [var.resolve(context) for var in self.vars_to_resolve]
                
                if takes_context:
                    args = [context] + resolved_vars
                else:
                    args = resolved_vars
                # TODO: store the object id in the cache value, then
                #       check if the timestamp name changes if we map an arbitrary value,
                #       eg timestamp_name % 1 then
                #
                #       if it stays the same, fetch the corresponding timestamp
                #       together with the cache value
                #       
                #       if the timestamp name is different (meaning it now has the blog id)
                #       fetch the cache value, extract the object id we have previously stored,
                #       map it to the timestamp name, then fetch the corresponding timestamp
                #
                #       then check expiration in the usual way
                blog_id = Blog.get_active().blog_id
                timestamp_keys = list() if not expire_timestamps else [get_key(blog_id, t) for t in expire_timestamps]
                cache_key = "%s.blog_%s.%s" % (
                    cache_key_prefix, blog_id, md5(''.join(a.encode('utf-8') if isinstance(a, unicode) else str(a) for a in resolved_vars)).hexdigest()
                )
                values = cache.get_many([cache_key] + timestamp_keys)
                value = values.get(cache_key)
                
                if value is not None:
                    timestamp, value = value
                    if CACHE_DEBUG:
                        value += "\n<!-- served on %s -->" % datetime.datetime.now()
                    del values[cache_key]
                    if values:
                        t = max(int(t) for t in values.values())
                        if t and timestamp > t:
                            return value
                    else:
                        return value
                    
                d = func(*args)
                
                try:
                    localize_template_value = None if not localize_template_by else Variable(localize_template_by).resolve(d)
                except VariableDoesNotExist:
                    localize_template_value = None

                if localize_template_value:
                    self.nodelist = self._nodelists.get(localize_template_value)
                
                if not getattr(self, 'nodelist', None):
                    from django.template.loader import get_template, select_template
                    
                    if isinstance(file_name, basestring) or not is_iterable(file_name):
                        _file_name = [file_name]
                    else:
                        _file_name = list(file_name)
                    
                    if localize_template_value:
                        __file_name = list()
                        for f in _file_name:
                            base, ext = os.path.splitext(f)
                            __file_name.append("%s_%s%s" % (base, localize_template_value, ext))
                            __file_name.append(f)
                        _file_name = __file_name
                    
                    t = select_template(_file_name)

                    if localize_template_value:
                        self._nodelists[localize_template_value] = t.nodelist

                    self.nodelist = t.nodelist
                
                new_context = context_class(d, autoescape=context.autoescape)

                csrf_token = context.get('csrf_token', None)
                if csrf_token is not None:
                    new_context['csrf_token'] = csrf_token

                value = self.nodelist.render(new_context)
                if CACHE_DEBUG:
                    value = ('<!-- begin %s -->' % cache_key) + value + ('\n<!--\nend %s\ncached on %s\n-->' % (cache_key, datetime.datetime.now()))
                cache.set(cache_key, (time.time(), value), CACHE_TIMEOUT)
                    
                return value

        compile_func = curry(generic_tag_compiler, params, defaults, getattr(func, "_decorated_function", func).__name__, InclusionNode)
        compile_func.__doc__ = func.__doc__
        register.tag(getattr(func, "_decorated_function", func).__name__, compile_func)
        return func
    
    return dec

