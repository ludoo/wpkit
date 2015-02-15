from django import template
from django.utils.safestring import mark_safe

from ..wp import content as content_lib


register = template.Library()


@register.filter(is_safe=True)
def wpkit_balance_tags(content):
    """Does not texturize text blocks"""
    return mark_safe(content_lib.balance_tags(content))


@register.filter(is_safe=True)
def wpkit_balance_tags_texturize(content):
    """Texturizes text blocks"""
    return mark_safe(content_lib.balance_tags(content, texturize=True))


@register.filter(is_safe=True)
def wpkit_convert_shortcodes(content):
    return mark_safe(content_lib.convert_shortcodes(content))


@register.filter(is_safe=True)
def wpkit_strip_shortcodes(content):
    return mark_safe(content_lib.strip_shortcodes(content))


@register.filter(is_safe=True)
def wpkit_texturize_block(content):
    """Texturizes a block of text without taking into account tags."""
    return mark_safe(content_lib.texturize_block(content))


@register.filter(is_safe=True)
def wpkit_autop(content):
    return mark_safe(content_lib.autop(content))


@register.filter(is_safe=True)
def wpkit_format_content(content):
    return mark_safe(content_lib.format_content(content))


@register.filter(is_safe=True)
def wpkit_auto_excerpt(post):
    return mark_safe(content_lib.auto_excerpt(post))


@register.filter(is_safe=True)
def wpkit_more_sub(content, post_id):
    return mark_safe(content_lib.POST_MORE_RE.sub(
        '<span id="more-%s"></span>' % post_id, content
    ))

@register.filter(is_safe=True)
def wpkit_formatted_part(post, part_name=None):
    return mark_safe(content_lib.formatted_part(post, part_name))
