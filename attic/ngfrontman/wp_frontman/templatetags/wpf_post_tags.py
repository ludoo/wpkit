# encoding: utf-8

from django import template
from django.db.models.query import QuerySet


register = template.Library()


@register.filter
def filter_image_attachments(attachments):
    return [a for a in attachments if a.mime_type.startswith('image/')]


@register.filter
def prefetch_postmeta(posts):
    if isinstance(posts, QuerySet):
        return posts.prefetch_postmeta()
    if posts:
        _posts = dict((p.id, p) for p in posts)
        for pm in posts[0].wp_blog.models.PostMeta.objects.filter(post__in=posts):
            p = _posts[pm.post_id]
            if not hasattr(p, 'wp_prefetched_postmeta'):
                p.wp_prefetched_postmeta = [pm]
            else:
                p.wp_prefetched_postmeta.append(pm)
    return posts
    
    
@register.filter
def prefetch_taxonomies(posts):
    if isinstance(posts, QuerySet):
        return posts.prefetch_taxonomies()
    if posts:
        _posts = dict((p.id, p) for p in posts)
        qs = posts[0].wp_blog.models.BasePostRelTaxonomy.objects.filter(
            basepost__in=posts
        ).select_related(
            'taxonomy', 'taxonomy__term', 'taxonomy__parent'
        )
        for t in qs:
            p = _posts[t.basepost_id]
            if not hasattr(p, 'wp_prefetched_taxonomies'):
                p.wp_prefetched_taxonomies = [t]
            else:
                p.wp_prefetched_taxonomies.append(t)
    return posts


@register.filter
def prefetch_attachments(posts):
    if isinstance(posts, QuerySet):
        return posts.prefetch_attachments()
    if posts:
        models = posts[0].wp_blog.models
        if not hasattr(models, 'Attachment'):
            return []
        _posts = dict((p.id, p) for p in posts)
        for a in models.Attachment.objects.filter(parent__in=posts).prefetch_postmeta():
            p = _posts[a.parent_id]
            if not hasattr(p, 'wp_prefetched_attachments'):
                p.wp_prefetched_attachments = [a]
            else:
                p.wp_prefetched_attachments.append(a)
    return posts
