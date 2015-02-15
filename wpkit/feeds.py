from django.contrib.syndication.views import Feed


class PostsFeed(Feed):
    
    def get_object(self, request, *args, **kw):
        return getattr(request, 'blog', None)

    def items(self, obj):
        if obj is None:
            return []
        return obj.models.Post.objects.posts().published()[:obj.options.posts_per_rss]
    
    def link(self, obj):
        return obj.home
    
    def description(self, obj):
        return u'Entries feed for %s' % obj.options.blogname
    
    def item_title(self, item):
        return item.title

    def item_description(self, item):
        # TODO: use a template
        if item._wp_blog.options.rss_use_excerpt:
            return item.auto_excerpt + u'[\u2026]'
        return item.formatted_part('content')

    def item_link(self, item):
        return item.url

    def item_author_name(self, item):
        return item.author.nicename

    def item_pubdate(self, item):
        return item.date
    
    def item_updateddate(self, item):
        return item.modified
