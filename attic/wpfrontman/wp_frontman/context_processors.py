

def blog(request):
    return dict(blog=getattr(request, 'blog', None))
