'''WP Frontman urlrules for blog '3', generated on 2011-03-30T13:41:55.887986'''

from django.conf.urls.defaults import *

from wpf.urls import urlpatterns as main_patterns


urlpatterns = patterns('wp_frontman.views',
    url('^blog3/$', 'index', name='wpf_index'),
    url('^blog3/page/(?P<page>[0-9]+)/$', 'index', name='wpf_index'),
    # url('^blog3/page(?P<page>[0-9]+)/$', 'index'),
    url('^blog3/(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})/(?P<slug>[^/]+)/$', 'post', name='wpf_post'),
    url('^blog3/(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})/(?P<slug>[^/]+)/page/(?P<page>[0-9]+)/$', 'post', name='wpf_post'),
    url('^blog3/(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})/(?P<slug>[^/]+)/trackback/$', 'trackback', name='wpf_trackback'),
    url('^blog3/(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/$', 'archives', name='wpf_archives'),
    url('^blog3/(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/page/(?P<page>[0-9]+)/$', 'archives', name='wpf_archives'),
    url('^blog3/(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/page(?P<page>[0-9]+)/$', 'archives'),
    url('^blog3/(?P<year>[0-9]{4})/$', 'archives', name='wpf_archives'),
    url('^blog3/(?P<year>[0-9]{4})/page/?(?P<page>[0-9]+)/$', 'archives', name='wpf_archives'),
    url('^blog3/author/(?P<slug>[^/]+)/$', 'author', name='wpf_author'),
    url('^blog3/author/(?P<slug>[^/]+)/page/?(?P<page>[0-9]+)/$', 'author', name='wpf_author'),
    url('^blog3/category/(?P<slug>[^/]+)/$', 'category', name='wpf_category'),
    url('^blog3/category/(?P<slug>[^/]+)/page/?(?P<page>[0-9]+)/$', 'category', name='wpf_category'),
    url('^blog3/search/$', 'search', name='wpf_search'),
    url('^blog3/search/(?P<q>.+)/$', 'search', name='wpf_search'),
    url('^blog3/search/(?P<q>.+)/page/?(?P<page>[0-9]+)/$', 'search', name='wpf_search'),
    url('^blog3/tag/(?P<slug>[^/]+)/$', 'tag', name='wpf_tag'),
    url('^blog3/tag/(?P<slug>[^/]+)/page/?(?P<page>[0-9]+)/$', 'tag', name='wpf_tag'),
    url('^blog3/feed/$', 'feed', name='wpf_feed'),
    url('^blog3/(?:feed/)?(?:feed|rdf|rss|rss2|atom)/$', 'feed'),
    url('^blog3/wp-(?:atom|feed|rdf|rss|rss2)\.php$', 'feed'),
    url('^blog3/comments/feed/$', 'feed_comments', name='wpf_feed_comments'),
    url('^blog3/comments/(?:feed/)?(?P<feed_type>feed|rdf|rss|rss2|atom)/$', 'feed_comments'),
    url('^blog3/wp-commentsrss2.php$', 'feed_comments'),
    url('^blog3/author/(?P<nicename>[^/]+)/feed/$', 'feed_author', name='wpf_feed_author'),
    url('^blog3/author/(?P<nicename>[^/]+)(?:/feed)?/(?P<feed_type>feed|rdf|rss|rss2|atom)/$', 'feed_author'),
    url('^blog3/(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})/(?P<slug>[^/]+)/feed/$', 'feed_post', name='wpf_feed_post'),
    url('^blog3/(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})/(?P<slug>[^/]+)/(?:feed/)?(?P<feed_type>feed|rdf|rss|rss2|atom)/$', 'feed_post'),
    #url('^blog3/category/(?P<slug>[^/]+)(?:/feed)?/(?P<feed_type>feed|rdf|rss|rss2|atom)/$', 'feed_category', name='wpf_feed_category'),
    #url('^blog3/search/(?P<q>.+)(?:/feed)?/(?P<feed_type>feed|rdf|rss|rss2|atom)/$', 'feed_search', name='wpf_feed_search'),
    #url('^blog3/tag/(?P<slug>[^/]+)(?:/feed)?/(?P<feed_type>feed|rdf|rss|rss2|atom)/$', 'feed_tag', name='wpf_feed_tag')
)


urlpatterns += main_patterns
