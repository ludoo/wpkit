import datetime

from mimetypes import guess_type

from django.conf import settings
from django.utils.module_loading import import_by_path
from django.core.paginator import Paginator, InvalidPage
from django.shortcuts import render
from django.http import HttpResponse, Http404

from feeds import PostsFeed
from wp.utils import kwargs_to_datetime


if hasattr(settings, 'WPKIT_PAGINATOR'):
    PAGINATOR_CLASS = import_by_path(settings.WPKIT_PAGINATOR, 'WpKit ')
else:
    PAGINATOR_CLASS = Paginator


FEED_POSTS = PostsFeed()


def index(request, page=1):
    # TODO: maybe check blog.options.page_on_front and react accordingly
    blog = request.blog
    paginator = PAGINATOR_CLASS(
        blog.models.Post.objects.published_posts(),
        blog.options.posts_per_page or 8
    )
    try:
        page = paginator.page(page)
    except InvalidPage:
        # TODO: raise 404?
        page = None
    
    return render(request, 'wpkit/index.html', {
        'page':page
    })

    
def post(request, **kw):
    
    qs = request.blog.models.Post.objects.posts().published()
    
    dt = kwargs_to_datetime(kw)
    if isinstance(dt, tuple):
        qs = qs.filter(date__range=dt)

    for k in ('slug', 'id'):
        if k in kw:
            qs = qs.filter(**{k:kw[k]})
    # TODO: category/tag/author/search?
    
    posts = list(qs)
    if len(posts) != 1:
        raise Http404("No such post (%s)" % len(posts))

    return render(request, 'wpkit/post.html', {
        'post':posts[0]
    })


def search(request):
    pass


def author(request):
    pass


def archive(request, **kw):
    
    blog = request.blog

    dt = kwargs_to_datetime(kw)
    if not isinstance(dt, tuple):
        raise Http404("No such date")
        
    paginator = PAGINATOR_CLASS(
        blog.models.Post.objects.published_posts().filter(date__range=dt),
        blog.options.posts_per_page or 8
    )
    
    try:
        page = paginator.page(kw.get('page', 1))
    except InvalidPage:
        page = None
    
    return render(request, 'wpkit/archive.html', {
        'monthly':'month' in kw, 'archive_date':dt[0].date(), 'page':page
    })


def taxonomy(request, taxonomy, slug, page=1):

    blog = request.blog

    try:
        taxonomy = blog.models.Taxonomy.objects.get(taxonomy=taxonomy, term__slug=slug)
    except blog.models.Taxonomy.DoesNotExist:
        raise Http404("No such object")
        
    # TODO: include children's posts for hierarchical taxonomies
    paginator = PAGINATOR_CLASS(
        taxonomy.posts.filter(post_type='post', status='publish'),
        blog.options.posts_per_page or 8
    )
    
    try:
        page = paginator.page(page)
    except InvalidPage:
        page = None
    
    return render(request, 'wpkit/taxonomy.html', {
        'taxonomy':taxonomy, 'page':page
    })
    

def media(request):
    pass


def feed(request):
    return FEED_POSTS(request)


def robots(request):
    pass


def favicon(request):
    pass


# deprecated
def feed_comments(request):
    pass

"""
def media(request, filepath):
    if filepath[-1] == '/':
        filepath = filepath[:-1]
    return _static_media(request, 'wp-content/blogs.dir/%s/files/%s' % (request.blog.blog_id, filepath))
    

def _static_media(request, path):
    if '..' in path:
        return HttpResponseBadRequest("File path forbidden")
    if not WPF_WP_ROOT:
        return HttpResponseServerError("Missing WPF_WP_ROOT setting")
    if path and path[0] == '/':
        # relative path, strip leading slash
        path = path[1:]
    abspath = os.path.join(WPF_WP_ROOT, path)
    mimetype = guess_type(abspath)
    if not mimetype[0]:
        return HttpResponseBadRequest("Unknown mimetype")
    if isinstance(abspath, unicode):
        abspath = abspath.encode('utf-8')
    if WPF_SENDFILE and not settings.DEBUG:
        # return the appropriate headers
        response = HttpResponse(mimetype=mimetype[0])
        response['X-Sendfile'] = abspath
        return response
    if not os.path.isfile(abspath):
        raise Http404("No such file %s" % abspath)
    return HttpResponse(file(abspath, 'rb'), mimetype=mimetype[0])
    

def favicon(request):
    return _static_media(request, request.blog.options['favicon_path'])


def robots(request):
    return _static_media(request, request.blog.options['robots_path'])
"""