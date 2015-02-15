from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django import template
from django.db import models

from wp_frontman.lib.utils import make_tree, prune_tree, s2i
from wp_frontman.blog import Blog
from wp_frontman.models import *
from wp_frontman.cache.tag_decorators import cached_inclusion_tag


register = template.Library()


@register.filter
def post_length_gt(post, args):
    return


@register.filter
def post_length(post, args):
    post_length = getattr(post, '_wpf_post_length', None)
    if post_length is None:
        lengths = dict(line=20, comment=180, comment_form=300, post_meta=300, num_chars=70)
        args = [int(a) for a in args.split(',')]
        for a in ('line', 'comment', 'comment_form'):
            try:
               lengths[a] = args.pop(0)
            except IndexError:
                pass
        post_length = lengths['post_meta']
        post_length += len(post.content_stripped) / lengths['num_chars'] * lengths['line']
        post_length += post.comment_count * lengths['comment']
        if post.comment_status == 'open':
            post_length += lengths['comment_form']
        post._wpf_post_length = post_length
    return post_length
        

@cached_inclusion_tag(register, 'wp_frontman/tags/sb_pages.html', takes_context=True, expire_timestamps=('page',))
def sb_pages(context, ordering=None, max_level=None, num=None):
    # TODO: change the model to Page once deferreds work properly with proxy models
    qs = BasePost.objects.pages().published().select_related('parent').defer(
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
    request = context.get('request')
    return dict(blog=Blog.get_active(), path=getattr(context.get('request'), 'path', None), pages=pages, max_level=max_level)


@cached_inclusion_tag(register, 'wp_frontman/tags/sb_recent_posts.html', expire_timestamps=('post',))
def sb_recent_posts(num=5, skip=0, exclude_id=None, title=None, keep_content=False, exclude_posts=None):
    if skip:
        start, end = skip, num+skip
    else:
        start, end = 0, num
    defer_list = ('date_gmt', '_excerpt', 'password')
    if not keep_content:
        defer_list += ('content', 'content_filtered', 'modified_gmt')
    qs = Post.objects.published().defer(*defer_list)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    if exclude_posts:
        qs = qs.exclude(id__in=[p.id for p in exclude_posts])
    return dict(blog=Blog.get_active(), posts=qs[start:end], title=title)

@cached_inclusion_tag(register, 'wp_frontman/tags/sb_top_commented.html', expire_timestamps=('post',))
def sb_top_commented(num=5, skip=0, exclude_id=None, title=None, keep_content=False):
    if skip:
        start, end = skip, num+skip
    else:
        start, end = 0, num
    defer_list = ('date_gmt', '_excerpt', 'password')
    if not keep_content:
        defer_list += ('content', 'content_filtered', 'modified_gmt')
    qs = Post.objects.published().defer(*defer_list)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    qs = qs.order_by('-comment_count')
    return dict(blog=Blog.get_active(), posts=qs[start:end], title=title)


@cached_inclusion_tag(register, 'wp_frontman/tags/sb_recent_comments.html', expire_timestamps=('comment',))
def sb_recent_comments(num=5, exclude_id=None):
    qs = BaseComment.objects.approved().select_related('base_post').defer(
        'base_post__date_gmt', 'base_post__content', 'base_post___excerpt',
        'base_post__password', 'base_post__modified_gmt', 'base_post__content_filtered'
    ).order_by('-id')
    if exclude_id:
        qs = qs.exclude(base_post__id=exclude_id)
    return dict(blog=Blog.get_active(), comments=qs[0:num])


@cached_inclusion_tag(register, 'wp_frontman/tags/sb_categories.html', expire_timestamps=('taxonomy',))
def sb_categories(ordering=None, max_level=None, num=None, parent_id=None, exclude=None, as_tree=True):
    # try a shortcut
    categories = None
    if not ordering and not max_level and not num and not exclude:
        tree = Category.get_all(as_tree=True)
        for k, v in tree.items():
            if k.term.slug == parent_id:
                categories = v
                prune_tree(categories, 'count')
                if not as_tree:
                    categories = categories.keys()
                break
    if not categories:
        if not ordering:
            ordering = Category._meta.ordering
        else:
            ordering = (ordering, ) + Category._meta.ordering
        qs = Category.objects.select_related('parent', 'term')
        if parent_id:
            if parent_id == 'root':
                qs = qs.filter(parent__isnull=True)
            else:
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
    return dict(blog=Blog.get_active(), categories=categories, max_level=max_level or None, as_sets=Blog.site.categories_as_sets)


@cached_inclusion_tag(register, 'wp_frontman/tags/sb_linkcategories.html', expire_timestamps=('taxonomy',))
def sb_linkcategories(ordering=None, max_level=None, num=None, parent_id=None, nested=False, toplevel_only=False):
    if not ordering:
        ordering = LinkCategory._meta.ordering
    else:
        ordering = (ordering, ) + LinkCategory._meta.ordering
    qs = LinkCategory.objects.select_related('parent', 'term')
    if toplevel_only:
        qs = qs.filter(parent__isnull=True)
    if parent_id:
        qs = qs.filter(parent__term__slug=parent_id)
    qs = qs.order_by(*ordering)
    if nested:
        categories = make_tree(qs)
        prune_tree(categories, 'count')
    else:
        categories = qs.filter(count__gt=0)
    if num:
        categories = categories[:num]
    return dict(blog=Blog.get_active(), categories=categories, max_level=max_level or None)


@cached_inclusion_tag(register, 'wp_frontman/tags/sb_archives_year.html', expire_timestamps=('post',))
def sb_archives_year(desc=False, orderby_count=False, num=None):
    return dict(blog=Blog.get_active(), archives=ArchiveYear.all(desc, orderby_count, num))


@cached_inclusion_tag(register, 'wp_frontman/tags/sb_archives_month.html', expire_timestamps=('post',))
def sb_archives_month(desc=False, orderby_count=False, num=None):
    return dict(blog=Blog.get_active(), archives=ArchiveMonth.all(desc, orderby_count, num))


@cached_inclusion_tag(register, 'wp_frontman/tags/sb_taxonomy_posts.html', expire_timestamps=('post',), localize_template_by='taxonomy_term.term.slug')
def sb_taxonomy_posts(slug, taxonomy='category', num=5, exclude=None, exclude_slice=None):
    try:
        taxonomy_term = TaxonomyTerm.objects.select_related('term').get(term__slug=slug, taxonomy=taxonomy)
    except ObjectDoesNotExist:
        return dict(taxonomy_term=None, posts=None)
    qs = PostTerms.objects.filter(
        term_taxonomy=taxonomy_term, post__post_type='post', post__status='publish'
    ).select_related('post').order_by('-post__id')
    if exclude:
        if isinstance(exclude, BasePost):
            exclude = [exclude]
        if exclude_slice:
            start, sep, end = exclude_slice.partition(':')
            try:
                if start and end:
                    exclude = exclude[int(start):int(end)]
                elif start:
                    exclude = exclude[int(start):]
                elif end:
                    exclude = exclude[:int(end)]
            except (TypeError, ValueError):
                pass
        qs = qs.exclude(post__id__in=[p.id for p in exclude])
    posts = [t.post for t in qs[:num]]
    return dict(blog=Blog.get_active(), taxonomy_term=taxonomy_term, posts=posts)


@cached_inclusion_tag(register, 'wp_frontman/tags/sb_taxonomy_pages.html', expire_timestamps=('page',), localize_template_by='taxonomy_term.term.slug')
def sb_taxonomy_pages(slug, taxonomy='post_tag', num=5):
    try:
        taxonomy_term = TaxonomyTerm.objects.select_related('term').get(term__slug=slug, taxonomy=taxonomy)
    except ObjectDoesNotExist:
        return dict(taxonomy_term=None, posts=None)
    pages = [t.post for t in PostTerms.objects.filter(
        term_taxonomy=taxonomy_term, post__post_type='page', post__status='publish'
    ).select_related('post').order_by('-post__id')[:num]]
    return dict(blog=Blog.get_active(), taxonomy_term=taxonomy_term, pages=pages)


@cached_inclusion_tag(register, 'wp_frontman/tags/sb_related_posts.html', expire_timestamps=('post',))
def sb_related_posts(post, num=5):
    """
    cursor.execute("select object_id, count(distinct term_taxonomy_id) as weight from wp_2_term_relationships t inner join wp_2_posts p on p.ID=t.object_id where term_taxonomy_id in (%s) and post_type='post' and post_status='publish' and object_id != %s group by object_id order by weight desc, object_id limit 5" % (', '.join(str(t) for t in tt_ids), p.id))
    """
    # defer some of the heavier post fields once the defer+annotate bug has been fixed
    posts = Post.objects.published().filter(tag__in=post.tags).exclude(id=post.id).annotate(weight=models.Count('tag')).order_by('-weight', '-date')[:num]
    return dict(blog=Blog.get_active(), posts=posts)


@cached_inclusion_tag(register, 'wp_frontman/tags/sb_page.html', expire_timestamps=('page',), localize_template_by='page.slug')
def sb_page(slug):
    try:
        page = Page.objects.get(slug=slug)
    except ObjectDoesNotExist:
        page=None
    return dict(blog=Blog.get_active(), page=page)


@cached_inclusion_tag(register, 'wp_frontman/tags/sb_links.html')
def sb_links():
    # TODO: support nested categories by using a tree as in the tags above,
    #       and adding links to each one in one sweep
    categories = dict()
    for rel in LinkCategories.objects.select_related('link', 'category').filter(link__visible='Y'):
        category = rel.category
        link = rel.link
        if not category.id in categories:
            categories[category.id] = category
            category.shortcuts = dict(links=list())
        else:
            category = categories[category.id]
        category.shortcuts['links'].append(link)
    categories = [c[1] for c in sorted([(c.term.name, c) for c in categories.values()])]
    return dict(blog=Blog.get_active(), categories=categories)


@cached_inclusion_tag(register, 'wp_frontman/tags/sb_tagcloud.html', expire_timestamps=('taxonomy',))
def sb_tagcloud(max_tags=30, size_max=1.2, size_avg=1, size_min=0.8, use_int=False, order_by=None, exclude=None, r=1, g=1, b=1, reorder_by_name=False):
    max_tags = s2i(max_tags, None)
    size_max = s2i(size_max, 1.2, cls=float)
    size_avg = s2i(size_avg, 1)
    size_min = s2i(size_min, 0.8, cls=float)
    r = s2i(r, 1, cls=float)
    g = s2i(g, 1, cls=float)
    b = s2i(b, 1, cls=float)
    tags = Tag.objects.select_related('term').order_by('-count')
    if exclude:
        tags = tags.exclude(term__slug__in=exclude.split(','))
    if order_by:
        tags = tags.order_by(order_by)
    if not tags:
        return dict(blog=Blog.get_active(), tags=list())
    if max_tags:
        tags = tags[:max_tags]
    nums = [t.count for t in tags]
    n_min = min(nums)
    n_max = max(nums)
    if not n_max:
        return dict(blog=Blog.get_active(), tags=list())
    if n_max == n_min:
        step = size_max / n_max
    else:
        step = (size_max - size_min) / float(n_max - n_min)
    use_rgb = len(set([r, g, b])) > 1
    for tag in tags:
        tag.cloud_size = size_min + (tag.count - n_min) * step
        if use_int:
            tag.cloud_size = int(tag.cloud_size)
        if use_rgb:
            tag.cloud_rgb = (int(round(tag.cloud_size*r)), int(round(tag.cloud_size*g)), int(round(tag.cloud_size*b)))
        else:
            tag.cloud_rgb = (tag.cloud_size, tag.cloud_size, tag.cloud_size)
    if reorder_by_name and tags:
        tags = [t[1] for t in sorted((t.term.name, t) for t in tags)]
    return dict(blog=Blog.get_active(), tags=tags)
