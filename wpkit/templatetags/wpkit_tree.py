import re

try:
    from collections import OrderedDict
except ImportError:
    from django.utils.datastructures import SortedDict as OrderedDict

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

from ..wp.trees import make_tree


register = template.Library()


@register.inclusion_tag('wpkit/tags/page_tree.html', takes_context=True)
def wpkit_page_tree(context, ordering=None, max_level=None, num=None):
    d = {'pages':[], 'max_level':max_level}
    blog = context.get('blog')
    if not blog:
        return d
    qs = blog.models.Post.objects.pages().published().select_related('parent').defer(
        'content', 'excerpt', 'password', 'modified_gmt', 'content_filtered',
        'parent__content', 'parent__excerpt', 'parent__password',
        'parent__modified_gmt', 'parent__content_filtered',
    )
    if ordering is not None:
        ordering = tuple([ordering, 'menu_order', 'title'])
    else:
        ordering = tuple(['menu_order', 'title'])
    qs = qs.order_by(*ordering)
    pages = make_tree(qs)
    d['pages'] = pages if not num else pages[:num]
    return d


@register.tag
def wpkit_rendertree(parser, token):
    """
    Render a nested tree. Partially inspired by django-mptt recursetree.
    
    Arguments:
    
    tree      - a nested tree composed of (default) nested dictionaries
                (dict or collections.OrderedDict or django.utils.datastructures.SortedDict)
                with the node as key and its direct descendants as values,
                or composed of nodes represented by regular dictionaries
                with a 'children' key containing its direct descendants
             
    max_level - an integer representing the optional maximum tree depth to render
    
    use_lists - a boolean flag indicating the type of tree passed as first argument
    
    
    Usage:
            <ul>
                {% rendertree tree %}
                    <li>
                        {{node.name}}
                        {% if not node.is_leaf_node %}
                            <ul>
                                {{children}}
                            </ul>
                        {% endif %}
                    </li>
                {% endrendertree %}
            </ul>
    """
    args = token.split_contents()
    tag_name = args.pop(0)
    if not args:
        raise template.TemplateSyntaxError("%s needs at least a tree as argument" % tag_name)
    tree_name = parser.compile_filter(args.pop(0))
    max_level = use_lists = None
    if args:
        max_level = parser.compile_filter(args.pop(0))
    if args:
        use_lists = parser.compile_filter(args.pop(0))
    if args:
        raise template.TemplateSyntaxError("%s accepts a  maximum of three arguments" % tag_name)
    
    template_fragment = parser.parse(('wpkit_endrendertree',))
    parser.delete_first_token()
    
    return RenderTreeNode(template_fragment, tree_name, max_level, use_lists)


class RenderTreeNode(template.Node):
    
    def __init__(self, template_fragment, root_name, max_level_name=None, use_lists_name=None):
        self.template_fragment = template_fragment
        self.root_name = root_name
        self.max_level_name = max_level_name
        self.use_lists_name = use_lists_name
        
    def _render_node(self, context, i, len_values, loop_dict, node, children, level=1, max_level=None, use_lists=False):
        buffer = list()
        context.push()
        if max_level is None or level < max_level:
            len_children = len(children)
            if not use_lists:
                for j, t in enumerate(children.items()):
                    k, v = t
                    context['node'] = k
                    context['level'] = level + 1
                    loop_dict_children = dict(parentloop=loop_dict)
                    buffer.append(self._render_node(
                        context, j, len_children, loop_dict_children, k, v, level+1, max_level, use_lists
                    ))
            else:
                for j, k in enumerate(children):
                    v = k.get('children', [])
                    context['node'] = k
                    context['level'] = level + 1
                    loop_dict_children = dict(parentloop=loop_dict)
                    buffer.append(self._render_node(
                        context, j, len_children, loop_dict_children, k, v, level+1, max_level, use_lists
                    ))
        loop_dict['counter0'] = i
        loop_dict['counter'] = i+1
        loop_dict['revcounter'] = len_values - i
        loop_dict['revcounter0'] = len_values - i - 1
        loop_dict['first'] = (i == 0)
        loop_dict['last'] = (i == len_values - 1)
        context['forloop'] = loop_dict
        context['node'] = node
        context['level'] = level
        context['is_leaf'] = not children
        context['children'] = mark_safe(u''.join(buffer))
        rendered = self.template_fragment.render(context)
        context.pop()
        return rendered
    
    def render(self, context):
        root = self.root_name.resolve(context)
        max_level = None
        if self.max_level_name is not None:
            max_level = self.max_level_name.resolve(context)
            try:
                max_level = int(max_level)
            except TypeError:
                pass
            except ValueError:
                raise template.TemplateSyntaxError("wpf_rendertree max_level argument must be an integer")
            max_level = max_level or None
        use_lists = False
        if self.use_lists_name is not None:
            try:
                use_lists = bool(int(self.use_lists_name.resolve(context)))
            except (TypeError, ValueError):
                pass
        if not use_lists:
            if not isinstance(root, (dict, OrderedDict)):
                raise template.TemplateSyntaxError("wpf_rendertree first argument must be a nested tree of ordered dicts")
        elif not isinstance(root, (list, tuple)):
            raise template.TemplateSyntaxError("wpf_rendertree first argument must be a list or tuple")
        loop_dict = dict(parentloop=dict())
        len_values = len(root)
        if not use_lists:
            return u''.join(
                self._render_node(
                    context, i, len_values, loop_dict, t[0], t[1], 1, max_level, use_lists
                ) for i, t in enumerate(root.items())
            )
        return u''.join(
            self._render_node(
                context, i, len_values, loop_dict, t, t.get('children', []), 1, max_level, use_lists
            ) for i, t in enumerate(root)
        )
