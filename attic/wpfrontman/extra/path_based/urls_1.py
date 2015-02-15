'''WP Frontman urlrules for blog '1', generated on 2011-03-30T13:41:55.832359'''

from django.conf.urls.defaults import *

from wpf.urls import urlpatterns as main_patterns


urlpatterns = patterns('wp_frontman.views',
    url('^$', 'index', name='wpf_index'),
    url('^page/(?P<page>[0-9]+)/$', 'index', name='wpf_index'),
    # url('^page(?P<page>[0-9]+)/$', 'index'),
    url('^(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})/(?P<slug>[^/]+)/$', 'post', name='wpf_post'),
    url('^(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})/(?P<slug>[^/]+)/page/(?P<page>[0-9]+)/$', 'post', name='wpf_post'),
    url('^(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})/(?P<slug>[^/]+)/trackback/$', 'trackback', name='wpf_trackback'),
    url('^(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/$', 'archives', name='wpf_archives'),
    url('^(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/page/(?P<page>[0-9]+)/$', 'archives', name='wpf_archives'),
    url('^(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/page(?P<page>[0-9]+)/$', 'archives'),
    url('^(?P<year>[0-9]{4})/$', 'archives', name='wpf_archives'),
    url('^(?P<year>[0-9]{4})/page/?(?P<page>[0-9]+)/$', 'archives', name='wpf_archives'),
    url('^author/(?P<slug>[^/]+)/$', 'author', name='wpf_author'),
    url('^author/(?P<slug>[^/]+)/page/?(?P<page>[0-9]+)/$', 'author', name='wpf_author'),
    url('^category/(?P<slug>[^/]+)/$', 'category', name='wpf_category'),
    url('^category/(?P<slug>[^/]+)/page/?(?P<page>[0-9]+)/$', 'category', name='wpf_category'),
    url('^search/$', 'search', name='wpf_search'),
    url('^search/(?P<q>.+)/$', 'search', name='wpf_search'),
    url('^search/(?P<q>.+)/page/?(?P<page>[0-9]+)/$', 'search', name='wpf_search'),
    url('^tag/(?P<slug>[^/]+)/$', 'tag', name='wpf_tag'),
    url('^tag/(?P<slug>[^/]+)/page/?(?P<page>[0-9]+)/$', 'tag', name='wpf_tag'),
    url('^feed/$', 'feed', name='wpf_feed'),
    url('^(?:feed/)?(?:feed|rdf|rss|rss2|atom)/$', 'feed'),
    url('^wp-(?:atom|feed|rdf|rss|rss2)\.php$', 'feed'),
    url('^comments/feed/$', 'feed_comments', name='wpf_feed_comments'),
    url('^comments/(?:feed/)?(?P<feed_type>feed|rdf|rss|rss2|atom)/$', 'feed_comments'),
    url('^wp-commentsrss2.php$', 'feed_comments'),
    url('^author/(?P<nicename>[^/]+)/feed/$', 'feed_author', name='wpf_feed_author'),
    url('^author/(?P<nicename>[^/]+)(?:/feed)?/(?P<feed_type>feed|rdf|rss|rss2|atom)/$', 'feed_author'),
    url('^(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})/(?P<slug>[^/]+)/feed/$', 'feed_post', name='wpf_feed_post'),
    url('^(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})/(?P<slug>[^/]+)/(?:feed/)?(?P<feed_type>feed|rdf|rss|rss2|atom)/$', 'feed_post'),
    #url('^category/(?P<slug>[^/]+)(?:/feed)?/(?P<feed_type>feed|rdf|rss|rss2|atom)/$', 'feed_category', name='wpf_feed_category'),
    #url('^search/(?P<q>.+)(?:/feed)?/(?P<feed_type>feed|rdf|rss|rss2|atom)/$', 'feed_search', name='wpf_feed_search'),
    #url('^tag/(?P<slug>[^/]+)(?:/feed)?/(?P<feed_type>feed|rdf|rss|rss2|atom)/$', 'feed_tag', name='wpf_feed_tag')
)


urlpatterns += main_patterns
