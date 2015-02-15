from django import template

from wp_frontman.blog import Blog
from wp_frontman.models import Post, Category


register = template.Library()


@register.filter
def wpf_add_taxonomy(posts):
    Post.fill_taxonomy_cache(posts)
    return posts


@register.filter
def wpf_add_taxonomy_by_count(posts):
    Post.fill_taxonomy_cache(posts, ordering=('-term_taxonomy__count', 'term_taxonomy__term'))
    return posts


@register.filter
def wpf_add_attachments(posts):
    Post._bootstrap_attachments(posts)
    return posts

