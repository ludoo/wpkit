def wpkit(request):
    return {
        'blog': getattr(request, 'blog', None)
    }
    