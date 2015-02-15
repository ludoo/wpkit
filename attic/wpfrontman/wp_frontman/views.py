import os

from urllib import quote, unquote
from mimetypes import guess_type

from django.http import HttpResponse, Http404, HttpResponseBadRequest, HttpResponseRedirect, HttpResponsePermanentRedirect, HttpResponseServerError
from django.template import RequestContext, loader
from django.shortcuts import render_to_response, get_object_or_404
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.utils.translation import ugettext as _

from wp_frontman.blog import Blog
from wp_frontman.models import *
from wp_frontman.forms import CommentForm, UserCommentForm, LoginForm, RegistrationForm
from wp_frontman.feeds import *
from wp_frontman.cache import get_key, get_object_key, get_object_value, set_object_value
from wp_frontman.cache.view_decorators import wpf_cache_page
from wp_frontman.lib.utils import get_date_range, get_set, make_tree
from wp_frontman.lib.wp_password_hasher import hash_password


WPF_SENDFILE = Blog.site.use_sendfile
WPF_WP_ROOT = Blog.site.wp_root
WPF_CATEGORIES_AS_SETS = Blog.site.categories_as_sets


def page_to_limits(page, num):
    if page is None:
        return 1, 0, num
    try:
        page = int(page)
    except (TypeError, ValueError):
        return 1, 0, num
    return page, (page-1)*num, (page-1)*num+num


def simple_paginator_vars(page, has_next, pattern_name, kw=None):
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


@wpf_cache_page(timestamps=('__all__',))
def index(request, page=None):
    if request.GET.get('preview') and request.GET.get('p'):
        # find out if the user can access this preview
        user = User.user_from_cookie(request)
        # TODO: verify nonce and /or check user capabilities
        if user or settings.DEBUG:
            try:
                post = BasePost.objects.get(id=request.GET.get('p'), post_type='post', status='draft')
            except ObjectDoesNotExist:
                pass
            else:
                request._cache_store_result = False
                return _post(request, post, None, 'wp_frontman/post.html')
    if 'q' in request.GET:
        q = request.GET['q']
        if q is None or not q.strip():
            return HttpResponseRedirect(reverse('wpf_index'))
        return HttpResponseRedirect(reverse('wpf_search', kwargs=dict(q=q)))
    page, start, end = page_to_limits(page, request.blog.posts_per_page)
    posts = list(Post.objects.published().select_related('author')[start:end+1])
    if len(posts) > request.blog.posts_per_page:
        posts = posts[:-1]
        has_next = True
    else:
        has_next = False
    if posts:
        Post.fill_taxonomy_cache(posts)
    return render_to_response(
        'wp_frontman/index.html',
        dict(posts=posts, **simple_paginator_vars(page, has_next, 'wpf_index')),
        context_instance=RequestContext(request)
    )


@wpf_cache_page(timestamps=('post', 'comment')) # don't care too much if the sidebar gets stale
def post(request, **kw):
    post = revision = None
    preview_id = request.GET.get('preview_id')
    if preview_id and request.GET.get('preview'):
        # checking the login first saves us a database request if we have no logged in user
        user_data = User.login_from_cookie(request)
        user = None if user_data is None else User.user_from_cookie(request, *user_data)
        if user:
            if request.GET.get('preview_nonce'):
                if User.verify_nonce(request, request.GET['preview_nonce'], 'post_preview_%s' % preview_id):
                    # ok, we have a preview id
                    revision = preview_id
            else:
                revision = preview_id
        
    # check the cache
    if not revision:
        key = get_object_key(request.blog.blog_id, 'post', kw)
        post = get_object_value(request.blog.blog_id, key, ('post', 'comment_post'))
    if post is None:
        try:
            post = Post.objects.get_from_keywords(kw)
        except ObjectDoesNotExist:
            raise Http404("No such post.")
        except DuplicatePermalink, e:
            return HttpResponsePermanentRedirect(e.args[0])
        if post.status == 'future':
            user = User.user_from_cookie(request)
            if not user:
                raise Http404("Not allowed")
            request._cache_store_result = False
        elif post and post.comment_status == 'open' and not revision:
            set_object_value(key, post)
    if revision:
        post.set_to_revision(revision)
    return _post(
        request, post, kw.get('comment_page'),
        ('wp_frontman/post_%s.html' % post.slug, 'wp_frontman/post.html')
    )


@wpf_cache_page(timestamps=('page', 'comment')) # don't care too much if the sidebar gets stale
def page(request, slug, comment_page=None):
    # stupid WordPress does not enforce unique slugs
    pages = Page.objects.filter(status__in=('publish', 'future')).select_related('author').filter(slug=slug, status='publish').order_by('-date')
    if not pages:
        raise Http404(_("No such page."))
    page = pages[0]
    if page.status == 'future':
        user = User.user_from_cookie(request)
        if not user:
            raise Http404("Not allowed")
    return _post(
        request, page, comment_page,
        ('wp_frontman/page_%s.html' % slug, 'wp_frontman/page.html')
    )


def _post(request, post, comment_page, templates):
    if post.comment_status == 'open' or post.status != 'publish':
        # prevent storing the response in the cache if we have to display the comment form
        request._cache_store_result = False
    comment_error = None
    form = None
    needs_login = False
    try:
        user_login, expiration, _hmac = User.login_from_cookie(request)
    except (TypeError, ValueError):
        user_login = user = None
    else:
        user = User.user_from_cookie(request, user_login, expiration, _hmac)
        if not user:
            user_login = None
    if post.comment_status == 'open':
        if request.method == 'POST':
            data = request.POST.copy()
            data['comment_parent'] = data.get('comment_parent') or request.GET.get('replytocom')
            #user = None if not user_login else User.user_from_cookie(request)
            if user:
                form = UserCommentForm(data)
            elif request.blog.comment_registration:
                # set the flag that tells our template to display the login/register fragment
                user_login = False
                needs_login = True
            else:
                user_login = False
                form = CommentForm(data)
            if form and form.is_valid():
                try:
                    comment = form.save(request, post, user)
                except ValueError, e:
                    #import sys
                    #import traceback
                    #file('/tmp/wpf_comment_error.log', 'a+').write(" ".join(traceback.format_tb(sys.exc_info()[2])) + "\n\n")
                    comment_error = _('Cannot post this comment') if not e.args else "Error when saving: %s" % e.args[0]
                else:
                    data = form.cleaned_data
                    response = HttpResponse()
                    if data.get('remember_info'):
                        path = reverse('wpf_index')
                        for k in ('author', 'author_email', 'author_url'):
                            v = data.get(k)
                            if v:
                                response.set_cookie('comment_%s_%s' % (k, request.blog.cookiehash), value=v.encode('utf-8'), path=path)
                    response.status_code = 302
                    if comment.approved == '1':
                        response['Location'] = comment.get_absolute_url()
                    else:
                        response['Location'] = post.get_absolute_url() + '#comments'
                    return response
            elif form and form['rawcontent'].errors:
                comment_error = _("Invalid or empty content")
        else:
            # only check that we have a cookie now, save querying the database
            # for when we have POST data
            if user_login:
                form = UserCommentForm()
            elif request.blog.comment_registration:
                # set the flag that tells our template to display the login/register fragment
                needs_login = True
            else:
                # show the default comment form
                initial = dict()
                if getattr(settings, 'WPF_COMMENTFORM_SET_INITIAL', True):
                    for k in initial.keys():
                        v = request.COOKIES.get("comment_%s_%s" % (k, request.blog.cookiehash))
                        if v:
                            initial[k] = unquote(v)
                form = CommentForm(initial=initial)
    #return render_to_response(
    response = HttpResponse(loader.render_to_string(
        templates,
        dict(
            post=post, form=form, comment_error=comment_error,
            page=comment_page, user_login=user_login, needs_login=needs_login
        ),
        context_instance=RequestContext(request)
    ))
    if post.ping_status == 'open' and request.blog.pingback_url:
        response['X-Pingback'] = request.blog.pingback_url
    return response
    

def trackback(request, **kw):
    pass
    

def _listing(request, obj, qs, page, templates, d, paginator_args):
    page, start, end = page_to_limits(page, request.blog.posts_per_page)
    posts = list(qs[start:end+1])
    if len(posts) > request.blog.posts_per_page:
        posts = posts[:-1]
        has_next = True
    else:
        has_next = False
    if posts:
        Post.fill_taxonomy_cache(posts)
    d['posts'] = posts
    d['obj'] = obj
    d.update(simple_paginator_vars(page, has_next, *paginator_args))
    return render_to_response(templates, d, context_instance=RequestContext(request))


@wpf_cache_page(timestamps=('post',))
def archives(request, year, month=None, page=None):
    label = year.rjust(4, '0')
    if month:
        label += month.rjust(2, '0')
    try:
        if month:
            dt_start, dt_end = get_date_range(year=year, month=month)
        else:
            dt_start, dt_end = get_date_range(year=year)
    except (TypeError, ValueError):
        raise Http404(_("No such archive."))
    qs = Post.objects.published().select_related('author').filter(date__range=(dt_start, dt_end))
    d = dict(year=year, month=month, label=label, dt_start=dt_start, dt_end=dt_end)
    paginator_d = dict(year=year)
    if month:
        paginator_d['month'] = month
    return _listing(
        request, d, qs, page, 'wp_frontman/archives.html',
        d,
        ('wpf_archives', paginator_d)
    )


@wpf_cache_page(timestamps=('post', 'page'))
def author(request, slug, page=None):
    author = get_object_or_404(User, nicename=slug)
    qs = author.basepost_set.posts().published().select_related('author')
    return _listing(
        request, author, qs, page,
        ('wp_frontman/author_%s.html' % slug, 'wp_frontman/author.html'),
        dict(author=author),
        ('wpf_author', dict(slug=slug))
    )


@wpf_cache_page(timestamps=('post',))
def category(request, slug, parents=None, page=None):
    slugs = [slug, quote(slug.encode('utf-8'))]
    slugs.append(slugs[-1].lower())
    if parents and WPF_CATEGORIES_AS_SETS:
        _parents = [t for t in parents.split('/') if t]
        for i, p in enumerate(_parents):
            if '%' in p:
                _parents[i] = unquote(p).decode('utf-8')
        parents_tree = Category.get_all(as_tree=True)
        branch = parents_tree
        for p in _parents:
            pq = quote(p.encode('utf-8'))
            try:
                root, branch = [(k, v) for k, v in branch.items() if k.term.slug in (p, pq, pq.lower())][0]
            except IndexError:
                raise Http404("No such category path.")
            if branch is None:
                break
        try:
            category = [c for c in branch if c.term.slug in slugs][0]
        except IndexError:
            raise Http404("No such category.")
    else:
        categories = Category.objects.select_related('term').filter(term__slug__in=slugs)
        if not categories:
            raise Http404("No such category.")
        category = categories[0]
    if WPF_CATEGORIES_AS_SETS:
        categories = [c.id for c in get_set(Category.objects.select_related('parent'), 'id', category.id)]
        qs = Post.objects.published().select_related('author').filter(base_taxonomy__id__in=categories)
    else:
        qs = category.posts.published().select_related('author')
    qs = qs.distinct()
    paginator_args = dict(slug=slug) if not parents or not WPF_CATEGORIES_AS_SETS else dict(slug=slug, parents=parents)
    return _listing(
        request, category, qs, page,
        ('wp_frontman/category_%s.html' % slug, 'wp_frontman/category.html'),
        dict(category=category),
        ('wpf_category', paginator_args)
    )

    
@wpf_cache_page(timestamps=('post',))
def taxonomy(request, taxonomy, slug, parents=None, page=None):
    # TODO: should probably make this more general and use it also for built-in taxonomies
    blog = Blog.get_active()
    custom_taxonomies = blog.options.get('wp_frontman', dict()).get('custom_taxonomies', dict())
    taxonomy_data = custom_taxonomies.get(taxonomy)
    if not custom_taxonomies.get('enabled') or not taxonomy_data:
        raise Http404("No such taxonomy.")
    slugs = [slug, quote(slug.encode('utf-8'))]
    slugs.append(slugs[-1].lower())
    """
    if parents and taxonomy_data['rewrite_hierarchical']:
        _parents = [t for t in parents.split('/') if t]
        for i, p in enumerate(_parents):
            if '%' in p:
                _parents[i] = unquote(p).decode('utf-8')
        parents_tree = Category.get_all(as_tree=True)
        branch = parents_tree
        for p in _parents:
            pq = quote(p.encode('utf-8'))
            try:
                root, branch = [(k, v) for k, v in branch.items() if k.term.slug in (p, pq, pq.lower())][0]
            except IndexError:
                raise Http404("No such category path.")
            if branch is None:
                break
        try:
            category = [c for c in branch if c.term.slug in slugs][0]
        except IndexError:
            raise Http404("No such category.")
    else:
        categories = Category.objects.select_related('term').filter(term__slug__in=slugs)
        if not categories:
            raise Http404("No such category.")
        category = categories[0]
    if WPF_CATEGORIES_AS_SETS:
        categories = [c.id for c in get_set(Category.objects.select_related('parent'), 'id', category.id)]
        qs = Post.objects.published().select_related('author').filter(base_taxonomy__id__in=categories)
    else:
        qs = category.posts.published().select_related('author')
    qs = qs.distinct()
    paginator_args = dict(slug=slug) if not parents or not WPF_CATEGORIES_AS_SETS else dict(slug=slug, parents=parents)
    return _listing(
        request, category, qs, page,
        ('wp_frontman/category_%s.html' % slug, 'wp_frontman/category.html'),
        dict(category=category),
        ('wpf_category', paginator_args)
    )
    """

#@wpf_cache_page(timestamps=('link_category',))
def links(request, slug, parents=None, page=None):
    slugs = [slug, quote(slug.encode('utf-8'))]
    slugs.append(slugs[-1].lower())
    if parents:
        _parents = [t for t in parents.split('/') if t]
        for i, p in enumerate(_parents):
            if '%' in p:
                _parents[i] = unquote(p).decode('utf-8')
        parents_tree = LinkCategory.get_all(as_tree=True)
        branch = parents_tree
        for p in _parents:
            pq = quote(p.encode('utf-8'))
            try:
                root, branch = [(k, v) for k, v in branch.items() if k.term.slug in (p, pq, pq.lower())][0]
            except IndexError:
                raise Http404("No such link category path.")
            if branch is None:
                break
        try:
            category = [c for c in branch if c.term.slug in slugs][0]
        except IndexError:
            raise Http404("No such link category.")
    else:
        categories = LinkCategory.objects.select_related('term').filter(term__slug__in=slugs)
        if not categories:
            raise Http404("No such link category.")
        category = categories[0]
    #qs = category.links.visible().select_related('author')
    categories = [c.id for c in get_set(LinkCategory.objects.select_related('parent'), 'id', category.id)]
    qs = Link.objects.visible().filter(categories__id__in=categories).order_by('name')
    page, start, end = page_to_limits(page, request.blog.posts_per_page)
    links = list(qs[start:end+1])
    if len(links) > request.blog.posts_per_page:
        links = links[:-1]
        has_next = True
    else:
        has_next = False
    d = dict(category=category, links=links)
    d.update(simple_paginator_vars(page, has_next, 'wpf_link_category', dict(slug=slug) if not parents else dict(slug=slug, parents=parents)))
    return render_to_response(
        ('wp_frontman/links_%s.html' % slug, 'wp_frontman/links.html'),
        d,
        context_instance=RequestContext(request)
    )


@wpf_cache_page(timestamps=('post',))
def tag(request, slug, page=None):
    _slug = quote(slug.encode('utf-8'))
    tags = Tag.objects.select_related('term').filter(term__slug__in=(slug, slug.lower(), _slug, _slug.lower()))
    if not tags:
        raise Http404("No such tag.")
    tag = tags[0]
    #try:
    #    tag = Tag.objects.select_related('term').get(term__slug=slug)
    #except ObjectDoesNotExist:
    #    raise Http404("No such tag.")
    qs = tag.posts.published().select_related('author')
    return _listing(
        request, tag, qs, page,
        ('wp_frontman/tag_%s.html' % slug, 'wp_frontman/tag.html'),
        dict(tag=tag),
        ('wpf_post_tag', dict(slug=slug))
    )


@wpf_cache_page(timestamps=('post',))
def search(request, q=None, page=None):
    q = q or request.GET.get('q')
    if q:
        qs = Post.objects.published().filter(models.Q(title__icontains=q)|models.Q(content__icontains=q)).select_related('author')
    else:
        qs = list()
    
    return _listing(
        request, q, qs, page,
        'wp_frontman/search.html',
        dict(q=q),
        ('wpf_search', dict(q=q))
    )


def feed_check_redirect(request, feed_type=None):
    options = Blog.get_active().options.get('wp_frontman', dict()).get('feedburner', dict())
    enabled = options.get('enabled')
    url = options.get('url' if not feed_type else '%s_url' % feed_type)
    feedburner_agent = 'feedburner' in request.META.get('HTTP_USER_AGENT', '').lower()
    if not enabled or not url or feedburner_agent:
        func = globals().get('feed' if not feed_type else 'feed_%s' % feed_type)
        return func(request)
    return HttpResponseRedirect(url)


@wpf_cache_page(timestamps=('post',))
def feed(request, feed_type='atom'):
    return posts_feed(request)


def feed_post(request, **kw):
    try:
        post = Post.objects.get_from_keywords(kw)
    except ObjectDoesNotExist:
        raise Http404("No such post.")
    return post_feed(request, post)


@wpf_cache_page(timestamps=('comment',))
def feed_comments(request, feed_type='atom'):
    return comments_feed(request)


@wpf_cache_page(timestamps=('post',))
def feed_author(request, **kw):
    return user_feed(request, **kw)


def user_login(request):
    if request.method == 'POST':
        data = request.POST.copy()
        form = LoginForm(data)
        if form.is_valid():
            redirect_to = request.GET.get('redirect_to')
            if not redirect_to:
                redirect_to = reverse('wpf_index')
            response = HttpResponseRedirect(redirect_to)
            user = form.cleaned_data['user']
            cookie = user.get_logged_in_cookie()
            if cookie:
                if not form.cleaned_data['rememberme']:
                    cookie['max_age'] = None
                response.set_cookie(**cookie)
            return response
    else:
        form = LoginForm()
    return render_to_response(
        'wp_frontman/user_login.html',
        dict(form=form),
        context_instance=RequestContext(request)
    )


def user_logout(request):
    redirect_to = request.GET.get('redirect_to')
    if not redirect_to:
        redirect_to = reverse('wpf_index')
    response = HttpResponseRedirect(redirect_to)
    for cookie in request.COOKIES:
        if cookie.startswith('wordpress_logged_in'):
            response.delete_cookie(cookie) #'wordpress_logged_in_%s' % Blog.site.siteurl_hash)
    return response


def user_registration(request):
    if request.method == 'POST':
        data = request.POST.copy()
        form = RegistrationForm(data)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('wpf_user_registration_message'))
    else:
        form = RegistrationForm()
    return render_to_response(
        'wp_frontman/user_registration.html',
        dict(form=form),
        context_instance=RequestContext(request)
    )


def user_registration_message(request):
    return render_to_response(
        'wp_frontman/user_registration_message.html',
        dict(),
        context_instance=RequestContext(request)
    )

    
def user_activation(request):
    activation_key = request.POST.get('key', request.GET.get('key'))
    if activation_key:
        try:
            s = UserSignup.objects.get(activation_key=activation_key, registered__gte=datetime.datetime.now() - datetime.timedelta(days=2))
        except ObjectDoesNotExist:
            pass
        else:
            # create user, mark signup as registered, and redirect to the user's profile
            user = s.activate()
            response = HttpResponseRedirect(reverse('wpf_user_profile'))
            response.set_cookie(**user.get_logged_in_cookie())
            return response
    return render_to_response(
        'wp_frontman/user_activation.html',
        dict(activation_key=activation_key),
        context_instance=RequestContext(request)
    )


def user_profile(request):
    user = User.user_from_cookie(request)
    if not user:
        return HttpResponseRedirect(reverse('wpf_user_login'))
    return render_to_response(
        'wp_frontman/user_profile.html',
        dict(user=User.user_from_cookie(request)),
        context_instance=RequestContext(request)
    )
    

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

    
#def feed_category(request, category, feed_type='atom'):
#    pass


#def feed_search(request, search, feed_type='atom'):
#    pass


#def feed_tag(request, tag, feed_type='atom'):
#    pass

