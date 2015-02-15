from django import template

from wp_frontman.wp_helpers import wp_nav_menu, month_archives, year_archives
from wp_frontman.lib.trees import make_tree, prune_tree
from wp_frontman.lib.utils import s2i


register = template.Library()


# TODO: use the cached_inclusion_tag decorator
@register.inclusion_tag('wp_frontman/tags/sb_pages.html', takes_context=True) #, expire_timestamps=('page',))
def wpf_sb_pages(context, blog=None, ordering=None, max_level=None, num=None):
    blog = blog or context.get('blog')
    if blog is None:
        return []
    qs = blog.models.Page.objects.published().select_related('parent').defer(
        'date_gmt', 'content', '_excerpt', 'password', 'modified_gmt', 'content_filtered',
        'parent__date_gmt', 'parent__content', 'parent___excerpt', 'parent__password',
        'parent__modified_gmt', 'parent__content_filtered',
    )
    if ordering is not None:
        ordering = tuple([ordering, 'menu_order', 'title'])
    else:
        ordering = tuple(['menu_order', 'title'])
    qs = qs.order_by(*ordering)
    pages = make_tree(qs)
    if num:
        pages = pages[:num]
    return dict(pages=pages, max_level=max_level)


# TODO: use the cached_inclusion_tag decorator
@register.inclusion_tag('wp_frontman/tags/sb_archives.html', takes_context=True) #, expire_timestamps=('page',))
def wpf_sb_archives(context, blog, yearly=False, asc=False, orderby_count=False, num=None):
    if yearly:
        return dict(archives=year_archives(blog, asc, orderby_count, num))
    return dict(archives=month_archives(blog, asc, orderby_count, num))


# TODO: use the cached_inclusion_tag decorator
@register.inclusion_tag('wp_frontman/tags/sb_categories.html', takes_context=True) #, expire_timestamps=('page',))
def wpf_sb_categories(context, blog, hierarchical=True):
    categories = blog.models.Category.objects.select_related('term', 'parent').order_by('term__name')
    return dict(categories=categories if not hierarchical else make_tree(categories))

    
# TODO: use the cached_inclusion_tag decorator
@register.inclusion_tag('wp_frontman/tags/sb_nav_menu.html', takes_context=True) #, expire_timestamps=('page',))
def wpf_sb_nav_menu(context, blog, menu_slug=None, root_id=None):
    menu, menu_items = wp_nav_menu(blog, menu_slug, root_id)
    return dict(menu=menu, menu_items=menu_items)
    
