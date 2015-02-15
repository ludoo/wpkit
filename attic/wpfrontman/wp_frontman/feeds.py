from django.conf import settings
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _

from models import Post, Page, Comment, User, Tag
from wp_frontman.blog import Blog


class AtomFeedWithBase(Atom1Feed):

    def root_attributes(self):
        d = super(AtomFeedWithBase, self).root_attributes()
        d.update({'xml:base':Blog.get_active().home})
        return d
    
    def item_attributes(self, item):
        return {'xml:base':Blog.get_active().home}
    

class PostsFeed(Feed):
    
    feed_type = AtomFeedWithBase
    description_template = 'wp_frontman/feeds/post_description.html'
        
    def title(self):
        return Blog.get_active().blogname
    
    def description(self):
        return Blog.get_active().blogdescription
    
    def link(self):
        return reverse('wpf_index')

    def items(self):
        posts = list(Post.objects.published()[:getattr(Blog.get_active(), 'posts_per_rss', 8)])
        Post.fill_taxonomy_cache(posts)
        return posts

    def item_title(self, item):
        return item.title
    
    def item_pubdate(self, item):
        return item.date
    
    def item_author_name(self, item):
        return item.author.nickname
    
    def item_categories(self, item):
        return [c.term.name for c in item.categories]

    def item_description(self, item):
        # TODO: find a better way of adding the post permalink for summarized posts
        if Blog.get_active().rss_use_excerpt and item.more:
            return item.summary_parsed_more # + u'[&hellip;]'
        return item.content_parsed
    

class CommentsFeed(Feed):

    feed_type = AtomFeedWithBase

    def title(self):
        return _(u'%s Comments') % Blog.get_active().blogname
    
    def description(self):
        return Blog.get_active().blogdescription
    
    def link(self):
        return reverse('wpf_index')

    def items(self):
        return list(Comment.objects.select_related('base_post').approved()[:getattr(Blog.get_active(), 'posts_per_rss', 8)])

    def item_title(self, item):
        return item.author + u' on ' + item.base_post.title
    
    def item_pubdate(self, item):
        return item.date
    
    def item_author_name(self, item):
        return item.author
    
    def item_description(self, item):
        return item.content
    

class PostFeed(CommentsFeed):
    
    feed_type = AtomFeedWithBase
    
    def title(self):
        return _(u'Comments for %s') % self._post.title
    
    def get_object(self, request, post):
        self._post = post
        return post
    
    def items(self, obj):
        return list(obj.basecomment_set.approved()[:Blog.get_active().posts_per_rss])
    
    
class UserFeed(PostsFeed):

    feed_type = AtomFeedWithBase

    def title(self):
        return u'Posts by %s' % self._user.nicename
    
    def get_object(self, request, nicename):
        self._user = get_object_or_404(User, nicename=nicename)
        return self._user
    
    def items(self, obj):
        return list(obj.basepost_set.posts().published()[:Blog.get_active().posts_per_rss])
    

def instantiate():
    t = list()
    for k, v in globals().items():
        if len(k) > 4 and k.endswith('Feed') and issubclass(v, Feed):
            name = k[:-4].lower() + '_feed'
            globals()[name] = v()
            t.append(name)
    return tuple(t)
            
__all__ = instantiate()
