import re

from hashlib import md5
from rfc3339 import rfc3339

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse


register = template.Library()


WIDONT_RE = re.compile(r'''(?<!>)\s+(?!<)''', re.U|re.M|re.S)


@register.filter
def wpkit_post_cssclasses(post):
    names = []
    names.append(u'post-%s' % post.id)
    names.append(u'type-%s' % post.post_type)
    names.append(u'status-%s' % post.status)
    if hasattr(post, 'format') and post.format:
        names.append(u'format-%s' % post.format.term.slug.replace('post-format-', ''))
    if hasattr(post, 'categories'):
        for category in post.categories:
            names.append(u'category-%s' % category.term.slug)
    if hasattr(post, 'tags'):
        for tag in post.tags:
            names.append(u'tag-%s' % tag.term.slug)
    return u' '.join(names)


@register.filter
def wpkit_rfc3339_utc(date):
    return rfc3339(date, utc=True, use_system_timezone=False)


@register.filter
@stringfilter
def wpkit_widont(text):
    """Adapted from typogrify's 'widont' filter, does not check tags"""
    tokens = WIDONT_RE.split(text)
    if len(tokens) <= 1:
        return text
    i = -1
    for t in reversed(tokens):
        if len(t) > 1:
            break
        i -= 1
    return mark_safe(u"%s&nbsp;%s" % (u' '.join(tokens[:i]), u'&nbsp;'.join(tokens[i:])))


@register.filter
def wpkit_md5(text, encoding='utf-8'):
    return md5(
        text if isinstance(text, str) else text.encode('utf-8', 'ignore')
    ).hexdigest()

    

@register.inclusion_tag('wpkit/tags/list_pagination.html', takes_context=True) #, expire_timestamps=('page',))
def wpkit_list_pagination(context, url_name, **kw):
    page = context.get('page')
    if not page:
        return {}
    previous_url = next_url = None
    if page.has_previous():
        previous_kw = kw.copy()
        previous_kw['page'] = page.previous_page_number()
        previous_url = reverse(url_name, kwargs=previous_kw)
    if page.has_next():
        next_kw = kw.copy()
        next_kw['page'] = page.next_page_number()
        next_url = reverse(url_name, kwargs=next_kw)
    return {
        'page':context['page'], 'previous_url':previous_url, 'next_url':next_url
    }
