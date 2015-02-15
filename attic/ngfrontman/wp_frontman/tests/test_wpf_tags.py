import unittest

try:
    from collections import OrderedDict
except ImportError:
    #from external.backports import OrderedDict
    from django.utils.datastructures import SortedDict as OrderedDict
from django.template import Template, Context, TemplateSyntaxError


class WpfTagsTestCase(unittest.TestCase):
    
    def testLoadTags(self):
        out = Template('{% load wpf_tags %}').render(Context())
        self.assertEqual(out, '')
        
    def testRenderTreeArgs(self):
        base = '{% load wpf_tags %}'
        # missing args or wrong number of args
        try:
            out = Template('{% load wpf_tags %}' '{% wpf_rendertree %}').render(Context())
        except TemplateSyntaxError, e:
            self.assertEqual(str(e), 'wpf_rendertree needs at least a tree as argument')
        try:
            out = Template('{% load wpf_tags %}' '{% wpf_rendertree 1 2 3 4 %}').render(Context())
        except TemplateSyntaxError, e:
            self.assertEqual(str(e), 'wpf_rendertree accepts a  maximum of three arguments')
        # invalid args
        try:
            out = Template('{% load wpf_tags %}' '{% wpf_rendertree 1 %}{% wpf_endrendertree %}').render(Context())
        except TemplateSyntaxError, e:
            self.assertEqual(str(e), 'wpf_rendertree first argument must be a nested tree of ordered dicts')
        try:
            out = Template('{% load wpf_tags %}' '{% wpf_rendertree 1 1 1 %}{% wpf_endrendertree %}').render(Context())
        except TemplateSyntaxError, e:
            self.assertEqual(str(e), 'wpf_rendertree first argument must be a list or tuple')
            
    def testRenderTreeOrderedDict(self):
        tree = {1: {4: {6: {11: {}}, 3: {}}}, 10: {}, 2: {}, 5: {7: {9: {}, 8: {}}}}
        out = Template(
            '{% load wpf_tags %}'
            '{% wpf_rendertree tree %}'
            '{{node}}{% if not is_leaf %}[ {{children}} ]{% if not forloop.last %}, {% endif %}{% else %}{% if not forloop.last %}, {% endif %}{% endif %}'
            '{% wpf_endrendertree %}'
        ).render(Context(dict(tree=tree)))
        self.assertEqual(out, '1[ 4[ 3, 6[ 11 ] ] ], 10, 2, 5[ 7[ 8, 9 ] ]')
        
    def testRenderTreeList(self):
        tree = [
            dict(id=1, children=[
                dict(id=4, children=[
                    dict(id=3, children=[]),
                    dict(id=6, children=[dict(id=11, children=[]),]),
                ]),
            ]),
            dict(id=10, children=[]),
            dict(id=2, children=[]),
            dict(id=5, children=[
                dict(id=7, children=[dict(id=8, children=[]), dict(id=9, children=[])]),
            ]),
        ]
        out = Template(
            '{% load wpf_tags %}'
            '{% wpf_rendertree tree 0 1 %}'
            '{{node.id}}{% if not is_leaf %}[ {{children}} ]{% if not forloop.last %}, {% endif %}{% else %}{% if not forloop.last %}, {% endif %}{% endif %}'
            '{% wpf_endrendertree %}'
        ).render(Context(dict(tree=tree)))
        self.assertEqual(out, '1[ 4[ 3, 6[ 11 ] ] ], 10, 2, 5[ 7[ 8, 9 ] ]')
        
        