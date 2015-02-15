#!/usr/bin/env python

import sys
import os

basepath = os.path.sep.join(os.path.abspath(os.path.dirname(__file__)).split(os.path.sep)[:-1])
sys.path.append(basepath)
os.environ['DJANGO_SETTINGS_MODULE'] = 'ngfrontman.settings'

from pprint import pprint

from django.db import connection, models

from wp_frontman.models import Site, Blog
from wp_frontman.wp_helpers import wp_nav_menu
from wp_frontman.lib.trees import make_tree


def queries():
    return [q['sql'] for q in connection.queries]


b = Blog(1)

print [f.name for f in b.models.Post._meta.fields]

qs = b.models.Post.objects.filter(status='publish').prefetch_children()

#print [p.id for p in qs]

post = qs[0]

print post.__class__
print [a for a in dir(post) if 'set' in a or 'related' in a]

print post.parent

#print qs[0].children

#print connection.queries[-1]['sql']

sys.exit(0)

"""
models = [(m.__name__, m.__bases__[0].__name__) for m in [getattr(b.models, a) for a in dir(b.models)] if isinstance(m, type) and issubclass(m, models.Model)]
max_name = max(len(m[0]) for m in models)
print "\n".join("%s %s" % (m[0].ljust(max_name), m[1]) for m in models)

print

for m in (b.models.BasePostTaxonomy, b.models.Category, b.models.LinkTaxonomy, b.models.LinkCategory):
    print m.__name__
    print m.objects.__class__.__name__
    print [(t.__class__.__name__, t.term.slug, t.taxonomy) for t in m.objects.select_related('term')]
    print connection.queries[-1]['sql']
    print
    
print b.models.Taxonomy._wp_taxonomy_for_model

print [a for a in dir(b.models.Post) if 'comment' in a]

for c in b.models.Comment.objects.select_related('post'):
    print c, c.id, c.post, c.post.id, c.post.post_type


p = b.models.Post.objects.published()[0]
print p.__class__.__name__, p.id, p.post_type
print "\n".join(repr((pp.name, pp.value, pp.post.__class__.__name__, pp.post.id, pp.post.post_type)) for pp in p.postmeta_set.select_related('post'))

pm = b.models.PostMeta.objects.all()[0]
print pm
print pm.post


#posts = list(b.models.Post.objects.published().wp_related_meta())
posts = list(b.models.Post.objects.published().wp_prefetch_related('PostMeta', 'post'))
print posts

for p in posts:
    print p.pk
    print ", ".join("%s:%s" % (meta.post_id, meta.name) for meta in p.wp_cache_postmeta)
    print

#print b.models.Post.objects.published().wp_related_meta()[0].wp_cache_postmeta
print b.models.Post.objects.published().wp_prefetch_related('PostMeta', 'post')[0].wp_cache_postmeta

print [
    (t.taxonomy, getattr(t.taxonomy, 'parent', None), t.taxonomy.term) for t in
    list(b.models.Post.objects.published().wp_prefetch_related('BasePostRelBasePostTaxonomy', 'basepost', 'wp_cache_taxonomies', ['taxonomy', 'taxonomy__term', 'taxonomy__parent']))[0].wp_cache_taxonomies
]

post = b.models.Post.objects.published().wp_prefetch_related('BasePostRelBasePostTaxonomy', 'basepost', 'wp_cache_taxonomies', ['basepost', 'taxonomy', 'taxonomy__term', 'taxonomy__parent'])[0]

print [(type(r.taxonomy), r.taxonomy.taxonomy, type(r.basepost), r.basepost.post_type, r.basepost.id) for r in post.wp_cache_taxonomies]

nav_menu, nav_menu_items = wp_nav_menu(b, 'custom-menu')

pprint(nav_menu_items)
#pprint(make_tree(nav_menu_items, 'menu_item_parent', from_dicts=True))

nav_menu, nav_menu_items = wp_nav_menu(b, 'custom-menu', root_id=4)

pprint(nav_menu_items)
"""
post = b.models.Post.objects.published()[0]
page = b.models.Page.objects.published()[0]

print [a for a in dir(post) if a.endswith('_set')]
print [a for a in dir(page) if a.endswith('_set')]

category = b.models.Category.objects.all()[0]
tag = b.models.PostTag.objects.all()[0]
thing = b.models.Thing.objects.all()[0]

print [a for a in dir(category) if a.endswith('_set')]
print [a for a in dir(tag) if a.endswith('_set')]
print [a for a in dir(thing) if a.endswith('_set')]

print "post.wp_taxonomies.all()"
print post.wp_taxonomies.all()
print queries()[-1]
print
print "post.wp_taxonomyrel_set.all()"
print post.wp_taxonomyrel_set.all()
print queries()[-1]
print
print "post.taxonomies"
print post.taxonomies
print queries()[-1]
print

"""
print post.id
print [r.taxonomy for r in post.postreltaxonomy_set.all()]

post = b.models.Post.objects.published().wp_prefetch_related(
    'BasePostRelTaxonomy', 'basepost', 'wp_cache_taxonomies',
    ['taxonomy', 'taxonomy__term', 'taxonomy__parent']
)[0]
print post.id
print post.taxonomies

print dir(post)

print "\n\n".join(queries())
"""
