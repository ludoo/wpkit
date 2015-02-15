from django import template


register = template.Library()


@register.inclusion_tag('wpkit/tags/sidebar_posts.html', takes_context=True) #, expire_timestamps=('page',))
def wpkit_sidebar_posts(context, num=None, page=None):
    blog = context.get('blog')
    num = num or blog.options.posts_per_page
    qs = blog.models.Post.objects.posts().published().order_by('-date_gmt').defer(
        'content', 'excerpt', 'password', 'modified_gmt', 'content_filtered'
    )
    if page and page.start_index() == 1:
        posts = qs[page.end_index():page.end_index()+num]
    else:
        posts = qs[:num]
    return {'posts':posts}


@register.inclusion_tag('wpkit/tags/sidebar_comments.html', takes_context=True) #, expire_timestamps=('page',))
def wpkit_sidebar_comments(context, num=5):
    blog = context.get('blog')
    qs = blog.models.Comment.objects.approved().select_related('post').order_by(
        '-date_gmt'
    ).defer('content')
    return {'comments':qs[:num]}


@register.inclusion_tag('wpkit/tags/sidebar_categories.html', takes_context=True) #, expire_timestamps=('page',))
def wpkit_sidebar_categories(context, num=None, order_by=None):
    blog = context.get('blog')
    qs = blog.models.Taxonomy.objects.filter(taxonomy='category').exclude(count=0)
    if order_by:
        qs = qs.order_by(*order_by.split(','))
    if num:
        categories = categories[:num]
    else:
        categories = list(qs)
    return {
        'categories':categories
    }


@register.inclusion_tag('wpkit/tags/sidebar_archives.html', takes_context=True) #, expire_timestamps=('page',))
def wpkit_sidebar_archives(context, num=None):
    blog = context.get('blog')
    qs = blog.models.Post.objects.posts().published().monthly_archives()
    if num:
        archives = qs[:num]
    else:
        archives = list(qs)
    return {'archives':archives}


@register.inclusion_tag('wpkit/tags/post_nav.html', takes_context=True) #, expire_timestamps=('page',))
def wpkit_post_nav(context, post):
    try:
        previous = type(post).objects.posts().published().filter(id__lt=post.id).order_by('-date_gmt')[0]
    except IndexError:
        previous = None
    try:
        next = type(post).objects.posts().published().filter(id__gt=post.id).order_by('date_gmt')[0]
    except IndexError:
        next = None
    return {
        'previous':previous, 'next':next
    }
