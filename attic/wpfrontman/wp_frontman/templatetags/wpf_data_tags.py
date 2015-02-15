from inspect import getargspec

from django import template

from wp_frontman.blog import Blog
from wp_frontman.models import Post, Category, LinkCategory
from wp_frontman.lib.utils import make_tree, prune_tree


register = template.Library()


if 'takes_context' in getargspec(register.simple_tag)[0]:
    # we are usign django 1.3, the stock simple_tag can take context
    simple_tag_with_context = register.simple_tag
else:

    from functools import partial
    
    def simple_tag_with_context(func=None, takes_context=None, name=None):
        
        def dec(func):
            params, xx, xxx, defaults = getargspec(func)
            if takes_context:
                if params[0] == 'context':
                    params = params[1:]
                else:
                    raise template.TemplateSyntaxError("Any tag function decorated with takes_context=True must have a first argument of 'context'")

            class SimpleNode(template.Node):
                def __init__(self, vars_to_resolve):
                    self.vars_to_resolve = map(template.Variable, vars_to_resolve)

                def render(self, context):
                    resolved_vars = [var.resolve(context) for var in self.vars_to_resolve]
                    if takes_context:
                        func_args = [context] + resolved_vars
                    else:
                        func_args = resolved_vars
                    return func(*func_args)

            function_name = name or getattr(func, '_decorated_function', func).__name__
            compile_func = partial(template.generic_tag_compiler, params, defaults, function_name, SimpleNode)
            compile_func.__doc__ = func.__doc__
            register.tag(function_name, compile_func)
            return func

        if func is None:
            # @register.simple_tag(...)
            return dec
        elif callable(func):
            # @register.simple_tag
            return dec(func)
        else:
            raise template.TemplateSyntaxError("Invalid arguments provided to simple_tag")


@simple_tag_with_context(takes_context=True)
def wpf_get_posts(context, num=None, skip=None, keep_content=False, context_var='posts'):
    blog = Blog.get_active()
    num = num or blog.posts_per_page
    skip = skip or 0
    defer_list = ('date_gmt', '_excerpt', 'password')
    if not keep_content:
        defer_list += ('content', 'content_filtered', 'modified_gmt')
    qs = Post.objects.published().defer(*defer_list)
    context[context_var] = qs[skip:skip+num]
    return ''


# TODO: use a single tag or at least a single function for all hierarchical taxonomy objects


@simple_tag_with_context(takes_context=True)
def wpf_get_post_categories(context, ordering=None, parents_only=False, num=None, parent_id=None, exclude=None, as_tree=False, context_var='categories'):
    if not ordering:
        ordering = Category._meta.ordering
    else:
        ordering = (ordering, ) + Category._meta.ordering
    qs = Category.objects.order_by(*ordering).select_related('parent', 'term')
    if parent_id:
        qs = qs.filter(parent__term__slug__in=parent_id.split(','))
    if exclude:
        qs = qs.exclude(term__slug__in=exclude.split(','))
    if parents_only:
        qs = qs.filter(parent__isnull=True)
    if as_tree:
        categories = make_tree(qs)
        prune_tree(categories, 'count')
    else:
        categories = qs.filter(count__gt=0)
    if num:
        categories = categories[:num]
    context[context_var] = categories
    return ''


@simple_tag_with_context(takes_context=True)
def wpf_get_link_categories(context, ordering=None, max_level=None, num=None, parent_id=None, exclude=None, as_tree=False, context_var='categories'):
    if not ordering:
        ordering = LinkCategory._meta.ordering
    else:
        ordering = (ordering, ) + LinkCategory._meta.ordering
    qs = LinkCategory.objects.select_related('parent', 'term')
    if parent_id:
        qs = qs.filter(parent__term__slug=parent_id)
    if exclude:
        qs = qs.exclude(term__slug__in=exclude.split(','))
    qs = qs.order_by(*ordering)
    if as_tree:
        categories = make_tree(qs)
        prune_tree(categories, 'count')
    else:
        categories = qs.filter(count__gt=0)
    if num:
        categories = categories[:num]
    context[context_var] = categories
    return ''
