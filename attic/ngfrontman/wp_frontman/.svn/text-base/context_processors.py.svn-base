
def wpf_blog(request):
    d = dict()
    if hasattr(request, 'blog'):
        blog = request.blog
        d['blog'] = blog
        d['blog_options'] = blog.options
        d['site'] = blog.site
        d['site_meta'] = blog.site.meta
    return d
