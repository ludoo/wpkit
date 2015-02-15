# encoding: utf8

import re

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

from wp_frontman.lib.utils import previous_next


register = template.Library()
widont_re = re.compile(r'''(?<!>)\s+(?!<)''', re.U|re.M|re.S)


@register.simple_tag
def post_summary_more(post, text=None, pre_text=None, post_text=None):
    return mark_safe(post.add_more(post.summary_parsed, text, pre_text, post_text))


@register.filter
def post_taxonomies_by_count(taxonomies, return_first=None):
    l = [t[1] for t in sorted([(t.count, t) for t in taxonomies], reverse=True)]
    if return_first:
        return None if not l else l[0]
    return l
    

@register.filter
@stringfilter
def wpf_widont(text):
    """Adapted from typogrify's 'widont' filter, does not check tags"""
    tokens = widont_re.split(text)
    if len(tokens) <= 1:
        return text
    i = -1
    for t in reversed(tokens):
        if len(t) > 1:
            break
        i -= 1
    return mark_safe(u"%s&nbsp;%s" % (u' '.join(tokens[:i]), u'&nbsp;'.join(tokens[i:])))


class RenderTreeNode(template.Node):
    
    def __init__(self, template_fragment, root_name, max_level_name=None):
        self.template_fragment = template_fragment
        self.root_name = root_name
        self.max_level_name = max_level_name
        
    def _render_node(self, context, i, len_values, loop_dict, node, children, level=1, max_level=None):
        buffer = list()
        context.push()
        if max_level is None or level < max_level:
            len_children = len(children)
            for j, t in enumerate(children.items()):
                k, v = t
                context['node'] = k
                context['level'] = level + 1
                loop_dict_children = dict(parentloop=loop_dict)
                buffer.append(self._render_node(context, j, len_children, loop_dict_children, k, v, level+1, max_level))
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
        if self.max_level_name is not None:
            max_level = self.max_level_name.resolve(context)
            try:
                max_level = int(max_level)
            except TypeError:
                max_level = None
            except ValueError:
                raise template.TemplateSyntaxError("rendertree max_level argument must be an integer")
        else:
            max_level = None
        loop_dict = dict(parentloop=dict())
        len_values = len(root)
        return ''.join(self._render_node(context, i, len_values, loop_dict, t[0], t[1], 1, max_level) for i, t in enumerate(root.items()))


@register.tag
def rendertree(parser, token):
    """
    Renders our simple trees. Partially inspired by django-mptt recursetree.
    
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
    args = token.contents.split()
    if len(args) == 2:
        root_name = parser.compile_filter(args[1])
        max_level = None
    elif len(args) == 3:
        root_name = parser.compile_filter(args[1])
        max_level = parser.compile_filter(args[2])
    else:
        raise template.TemplateSyntaxError("rendertree accepts only a tree root and an optional maximum level")
    
    template_fragment = parser.parse(('endrendertree',))
    parser.delete_first_token()
    
    return RenderTreeNode(template_fragment, root_name, max_level)
