#!/usr/bin/env python

import sys
import os

basepath = os.path.sep.join(os.path.abspath(os.path.dirname(__file__)).split(os.path.sep)[:-1])
sys.path.append(basepath)
os.environ['DJANGO_SETTINGS_MODULE'] = 'ngfrontman.settings'

from pprint import pprint

from django.db import connection, models

from wp_frontman.models import Site, Blog
from wp_frontman.wp_models import BasePost
from wp_frontman.lib.wp_rewrite_rules import convert_wp_rules


def queries():
    return [q['sql'] for q in connection.queries]


Blog.site = Site(using='test_multi', mu=True)
b1 = Blog.factory(1)
b2 = Blog.factory(2)

for m in dir(b1.models):
    model = getattr(b1.models, m)
    if not isinstance(model, models.base.ModelBase) or BasePost not in model.__bases__:
        continue
    print model.__name__
    print '-'*len(model.__name__)
    print [a for a in dir(model) if a.endswith('_set')]
    print
    