# encoding: utf-8

from django.test import TestCase
from django_nose.tools import *

from wpkit.wp import content
from .. import Differ


BALANCE_TESTS = (
    (
        '<p> <p>Test 0</p>',
        False,
        '<p> </p><p>Test 0</p>'
    ),
    (
        '<p>Test 1 <i>abc <b>nested tags</b> and </p>\n<p>Unbalanced <a>tags</a>',
        False,
        '<p>Test 1 <i>abc <b>nested tags</b> and </i></p>\n<p>Unbalanced <a>tags</a></p>'
    ),
    (
        '<p>Test 2 <i>abc <b>nested </i>tags</b> and </p>\n<p>Unbalanced <a>tags</a>',
        False,
        '<p>Test 2 <i>abc <b>nested </b></i>tags and </p>\n<p>Unbalanced <a>tags</a></p>'
    ),
    (
        '<p>Test 2 <i>abc <b>nested </i>tags <br /></b> and </p>\n<p>Unbalanced <a>tags</a>',
        False,
        '<p>Test 2 <i>abc <b>nested </b></i>tags <br /> and </p>\n<p>Unbalanced <a>tags</a></p>'
    ),
    (
        '<p>Test 2 <i>abc <b>nested </i>tags <br></b> and </p>\n<p>Unbalanced <a>tags</a>',
        False,
        '<p>Test 2 <i>abc <b>nested </b></i>tags <br/> and </p>\n<p>Unbalanced <a>tags</a></p>'
    ),
    (
        '''<p>Test 1-2 <i>abc's <b>"nested tags"</b> -- and </p>\n<p>Unbalanced <a>tags</a>''',
        True,
        u'<p>Test 1-2 <i>abc’s <b>“nested tags”</b> — and </i></p>\n<p>Unbalanced <a>tags</a></p>'
    ),
    (
        '''<p>Test 1-2 <i>abc's <b>"nested tags"</b> -- and </p>\n<pre>Unbalanced <a>tags'</a>''',
        True,
        u'<p>Test 1-2 <i>abc’s <b>“nested tags”</b> — and </i></p>\n<pre>Unbalanced <a>tags\'</a></pre>'
    ),
    (
        u'''<img class="post" src="/wp-content/blogs.dir/1/eurostar.jpg" align="left" width="240" height="180" />Vi sarà capitato di salire su un Eurostar la mattina ancora insonnoliti, o  a fine pomeriggio stanchi dopo una giornata di lavoro in trasferta, e conquistato l'agognato posto vicino al finestrino rannicchiarvi e cascare in un sonno profondo. E vi sarà anche capitato di svegliarvi di soprassalto per un rumore sferragliante qualche centimetro accanto alle vostre orecchie.''',
        True,
        u'''<img class="post" src="/wp-content/blogs.dir/1/eurostar.jpg" align="left" width="240" height="180" />Vi sarà capitato di salire su un Eurostar la mattina ancora insonnoliti, o  a fine pomeriggio stanchi dopo una giornata di lavoro in trasferta, e conquistato l’agognato posto vicino al finestrino rannicchiarvi e cascare in un sonno profondo. E vi sarà anche capitato di svegliarvi di soprassalto per un rumore sferragliante qualche centimetro accanto alle vostre orecchie.'''
    )
    # ...
)

TXTR_BLOCK_TESTS = (
    (
        '''WP's a "great" app, PHP rocks, and code is poetry...''',
        u'WP’s a “great” app, PHP rocks, and code is poetry…'
    ),
    (
        u'''Vi sarà capitato di salire su un Eurostar la mattina ancora insonnoliti, o  a fine pomeriggio stanchi dopo una giornata di lavoro in trasferta, e conquistato l'agognato posto vicino al finestrino rannicchiarvi e cascare in un sonno profondo. E vi sarà anche capitato di svegliarvi di soprassalto per un rumore sferragliante qualche centimetro accanto alle vostre orecchie.''',
        u'''Vi sarà capitato di salire su un Eurostar la mattina ancora insonnoliti, o  a fine pomeriggio stanchi dopo una giornata di lavoro in trasferta, e conquistato l’agognato posto vicino al finestrino rannicchiarvi e cascare in un sonno profondo. E vi sarà anche capitato di svegliarvi di soprassalto per un rumore sferragliante qualche centimetro accanto alle vostre orecchie.'''
    ),
    (
        'This comment <!--abc--> should not be converted, nor should this one <!-- ab c -->',
        'This comment <!--abc--> should not be converted, nor should this one <!-- ab c -->'
    ),
)

AUTOP_TESTS = (
    (
        '''Test 1.\nSecond line\n\n<br />Third line.''',
        '''<p>Test 1.<br />\nSecond line</p>\n<p>Third line.</p>\n'''
    ),
    (
        '''Test 2.\n\n<pre>Second line</pre>\n\nThird line.''',
        '''<p>Test 2.</p>\n<pre>Second line</pre>\n<p>Third line.</p>\n'''
    ),
)


class TestContent(TestCase):
    
    def test_balance_tags(self):
        for test, texturize, expected in BALANCE_TESTS:
            result = content.balance_tags(test, texturize)
            if result != expected:
                raise ValueError(Differ(expected=expected, result=result))

    def test_texturize_block(self):
        for test, expected in TXTR_BLOCK_TESTS:
            result = content.texturize_block(test)
            if result != expected:
                raise ValueError(Differ(expected=expected, result=result))

    def test_autop(self):
        for test, expected in AUTOP_TESTS:
            result = content.autop(test)
            if result != expected:
                raise ValueError(Differ(expected=expected, result=result))
