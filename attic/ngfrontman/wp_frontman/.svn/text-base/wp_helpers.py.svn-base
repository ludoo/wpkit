"""Assorted functions to deal with specific WP tasks or objects that don't fit anywhere else"""

import datetime
import warnings

from django.db import models
from django.core.urlresolvers import reverse


def wp_nav_menu(blog, menu_slug, root_id=None):
    """Return a tree of menu items for a given menu"""
    if not hasattr(blog.models, 'NavMenu'):
        raise ConfigurationError("Blog %s has no NavMenu model")
    if not hasattr(blog.models.NavMenu, 'navmenuitem_set'):
        raise ConfigurationError("Blog %s has no NavMenuItem related manager in the NavMenu model")
    # don't trap
    try:
        menu = blog.models.NavMenu.objects.select_related('term').get(term__slug=menu_slug)
    except ObjectDoesNotExist:
        raise ValueError("No such menu.")
    menu_items = list()
    menu_map = dict(root=list())
    item_posts = set()
    item_taxonomies = set()
    qs = menu.navmenuitem_set.prefetch_postmeta().defer('content', 'content_filtered')
    for post in qs:
        menu_item = dict(
            id=post.id, label=post.title, title=post.title, menu_order=post.menu_order,
            object=None
        )
        for meta in post.wp_prefetched_postmeta:
            name = str(meta.name.replace('_menu_item_', ''))
            value = meta.value
            if name in ('object_id', 'menu_item_parent'):
                value = None if not value else int(value)
            elif name == 'classes':
                continue
            else:
                value = None if not value else value
            if name == 'object':
                name = 'object_type'
            if name == 'menu_item_parent':
                name = 'parent'
            menu_item[name] = value
        if menu_item['type'] == 'post_type':
            item_posts.add((menu_item['object_type'], menu_item['object_id']))
        elif menu_item['type'] == 'taxonomy':
            item_taxonomies.add((menu_item['object_type'], menu_item['object_id']))
        menu_items.append(menu_item)
        if menu_item['parent']:
            menu_map.setdefault(menu_item['parent'], list()).append((post.menu_order, menu_item))
        else:
            menu_map['root'].append((post.menu_order, menu_item))

    if item_posts:
        item_posts = dict(
            (p.id, p) for p in blog.models.BasePost.objects.filter(
                id__in=[t[1] for t in item_posts]
            ).defer(
                'content', 'content_filtered', '_excerpt'
            )
        )
    if item_taxonomies:
        item_taxonomies = dict(
            ((t.term_id, t.taxonomy), t) for t in blog.models.Taxonomy.objects.filter(
                term__id__in=[t[1] for t in item_taxonomies]
            ).select_related('term')
        )
    
    for menu_item in menu_items:
        menu_item['children'] = [l[1] for l in sorted(menu_map.get(menu_item['id'], list()))]
        if menu_item['type'] == 'custom':
            continue
        if menu_item['type'] == 'post_type':
            obj = item_posts[menu_item['object_id']]
            if obj.post_type != menu_item['object_type']:
                warnings.warn(
                    "Menu item %s has post type '%s', but post %s has object type '%s'",
                    (menu_item['id'], menu_item['object_type'], obj.id, obj.post_type)
                )
            menu_item['object'] = obj
            menu_item['title'] = obj.title
            menu_item['url'] = obj.get_absolute_url()
        elif menu_item['type'] == 'taxonomy':
            obj = item_taxonomies[(menu_item['object_id'], menu_item['object_type'])]
            menu_item['object'] = obj
            menu_item['title'] = obj.term.name
            menu_item['url'] = obj.get_absolute_url()

    if root_id:
        # slightly inefficient, but who cares...
        try:
            return menu, [l[1] for l in sorted(menu_map[int(root_id)])]
        except KeyError:
            raise ValueError("No item in menu '%s' with id of '%s'." % (menu_slug, root_id))
            
    # type = post_type | taxonomy
    return menu, [l[1] for l in sorted(menu_map['root'])]


def month_archives(blog, asc=False, orderby_count=False, num=None):
    ordering = ('-year', '-month') if not asc else ('year', 'month')
    if orderby_count:
        ordering = ('-id__count',) + ordering
    qs = blog.models.Post.objects.published().extra(
        select=dict(year='year(post_date)', month='month(post_date)')
    ).values_list('year', 'month').annotate(models.Count('id')).order_by(*ordering)
    if num is not None:
        qs = qs[:num]
    archives = []
    for year, month, count in qs:
        archives.append(dict(
            year=year, month=month, count=count,
            dt=datetime.date(year=year, month=month, day=1),
            get_absolute_url=reverse('wpf_archive', kwargs=dict(year='%04d' % year, month='%02d' % month))
        ))
    return archives


def year_archives(blog, asc=False, orderby_count=False, num=None):
    ordering = ('-year',) if not asc else ('year',)
    if orderby_count:
        ordering = ('-id__count',) + ordering
    qs = blog.models.Post.objects.published().extra(
        select=dict(year='year(post_date)')
    ).values_list('year').annotate(models.Count('id')).order_by(*ordering)
    if num is not None:
        qs = qs[:num]
    archives = []
    for year, count in qs:
        archives.append(dict(
            year=year, month=1, count=count,
            dt=datetime.date(year=year, month=1, day=1),
            get_absolute_url=reverse('wpf_archive', kwargs=dict(year='%04d' % year))
        ))
    return archives
