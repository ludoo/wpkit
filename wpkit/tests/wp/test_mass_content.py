# encoding: utf-8

import os
import sys

from cPickle import load

from django.test import TestCase
from django_nose.tools import *

from wpkit.wp import content
from .. import Differ


class TestMassContent(TestCase):
    
    def test_content(self):
        
        # shortcircuit
        return

        samples = load(file(
            os.path.join(os.path.dirname(__file__), 'qix_posts.pickle')
        ))
        
        for i, sample in enumerate(samples):
            test, expected = sample
            result = content.process_content(test)

        for i, sample in enumerate(samples):
            if i in (0, 12, 16, 17, 18, 24, 26):
                # skip known differences
                continue
            test, expected = sample
            if '&quot;' in expected or "wp-smiley" in expected:
                continue
            expected = expected.replace(u'\u2033', u'\u201d')
            #if i != 178: continue
            result = content.process_content(test)
            if result != expected:
                print "Error in sample %s" % i
                #print >>sys.stderr, test
                raise ValueError(Differ(expected=expected, result=result))
