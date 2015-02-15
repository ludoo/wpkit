from django.http import HttpResponse, Http404, HttpResponseBadRequest, HttpResponseRedirect, HttpResponsePermanentRedirect, HttpResponseServerError
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.core.urlresolvers import reverse


def _start_end_from_page(page, num):
    if page is None:
        return 1, 0, num
    try:
        page = int(page)
    except (TypeError, ValueError):
        return 1, 0, num
    return page, (page-1)*num, (page-1)*num+num


def _paginator_vars(page, has_next, pattern_name, kw=None):
    kw = kw or dict()
    page_previous_url = page_next_url = None
    page_next = None
    page_previous = None if page == 1 else page - 1
    if page_previous == 1:
        page_previous_url = reverse(pattern_name, kwargs=kw)
        if not page_previous_url.endswith('/'):
            page_previous_url + '/'
    elif page_previous > 1:
        kw['page'] = page_previous
        page_previous_url = reverse(pattern_name, kwargs=kw)
    if has_next:
        kw['page'] = page_next = page + 1
        page_next_url = reverse(pattern_name, kwargs=kw)
    return dict(
        page=page, page_previous=page_previous, page_next=page_next,
        page_previous_url=page_previous_url, page_next_url=page_next_url
    )


# TODO: cache decorator
def index(request, page=None):
    # TODO: check for preview
    page, start, end = _start_end_from_page(page, request.blog.options['posts_per_page'])
    posts = list(request.blog.models.Post.objects.published().select_related('author')[start:end+1]) #.prefetch_taxonomies()[start:end+1])
    if len(posts) > request.blog.options['posts_per_page']:
        posts = posts[:-1]
        has_next = True
    else:
        has_next = False
    return render_to_response(
        'wp_frontman/index.html',
        dict(posts=posts, **_paginator_vars(page, has_next, 'wpf_index')),
        context_instance=RequestContext(request)
    )


def favicon(request):
    blog = request.blog
    opts = blog.options['wp_frontman'].get('favicon', dict())
    if not opts.get('favicon_handling'):
        # we should never get here, as the favicon.ico file should be managed
        # by the web server
        return HttpResponseServerError("WP Frontman is configured not to handle the favicon.ico file.")
    favicon_file = opts.get('favicon_file')
    if blog.site.meta['wp_frontman']['use_sendfile']:
        response = HttpResponse(mimetype='image/x-icon')
        response['X-Sendfile'] = favicon_file
        return response
    try:
        favicon = file(favicon_file, 'rb').read()
    except (OSError, IOError), e:
        response = HttpResponseServerError("Error reading favicon file '%s': %s" % (favicon_file, e))
    else:
        response = HttpResponse(favicon, mimetype='image/x-icon')
    return response
    

def robots(request):
    blog = request.blog
    opts = blog.options['wp_frontman'].get('favicon', dict())
    if not opts.get('robots_handling'):
        # we should never get here, as the robots.txt file should be managed
        # by the web server
        return HttpResponseServerError("WP Frontman is configured not to handle the robots.txt file.")
    robots_file = opts.get('robots_file')
    if blog.site.meta['wp_frontman']['use_sendfile']:
        response = HttpResponse(mimetype='text/plain')
        response['X-Sendfile'] = robots_file
        return response
    try:
        robots = file(robots_file, 'rb').read()
    except (OSError, IOError), e:
        response = HttpResponseServerError("Error reading robots file '%s': %s" % (robots_file, e))
    else:
        response = HttpResponse(robots, mimetype='text/plain')
    return response

    
def post(request, **kw):
    return


def archives(request):
    return


def taxonomy(request):
    return


def feed(request):
    return


def feed_comments(request):
    return


def search(request):
    return


def author(request):
    return


def media(request):
    return
