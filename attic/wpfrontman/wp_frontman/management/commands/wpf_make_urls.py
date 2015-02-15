import os
import sys
import datetime

from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from wp_frontman.blog import Blog


class Command(BaseCommand):
    
    option_list = BaseCommand.option_list + (
        make_option(
            "--strip-blog-from-default", action="store_true", dest="strip_blog", default=False,
            help="strip the 'blog' prefix WP adds to post permalinks in the default blog"
        ),
        make_option(
            "--prepend-main-rules", action="store_true", dest="prepend_main", default=False,
            help="prepend urlrules defined in settings.py to blog urls"
        ),
        make_option(
            "--append-main-rules", action="store_true", dest="append_main", default=False,
            help="append urlrules defined in settings.py to blog urls"
        ),
        make_option(
            "--dir", type="str", dest="dir", default=None,
            help="where to write the generated files, defaults to 'wpf_blogs' in the toplevel Django app"
        ),
        make_option(
            "--force", action="store_true", dest="force", default=False,
            help="overwrite urlrules files if already present, create destination folder if missing"
        ),
        make_option(
            "--check-feed-redirect", action="store_true", dest="feed_redirect", default=False,
            help="use settings from the wpf_feedburner plugin to check for feed redirection"
        ),
        make_option(
            "--search-base", type="str", dest="search_base", default=None,
            help="override the search base (path prefix for search pages), defaults to WP's default of 'search'"
        ),
        make_option(
            "--links-base", type="str", dest="links_base", default='links',
            help="base path to use for link categories, defaults to 'links'"
        ),
        make_option(
            "--search-view", type="str", dest="search_view", default='wp_frontman.views.search',
            help="override the search view, defaults to wp_frontman.views.search"
        ),
        make_option(
            "--default-feed-url", type="str", dest="default_feed", default=None,
            help="default feed url for reversing urlrules"
        ),
        make_option(
            "--additional-feeds", type="str", dest="additional_feeds", default=None,
            help="feed paths separated by commas used to set up additional url rules redirecting to the main feed"
        ),
    )
    usage = lambda s, sc: "Usage: ./manage.py %s [options] [blog_id]" % sc
    help = "Creates Django urlrules from WP options for WPFrontman blogs."
    requires_model_validation = False
    
    def handle(self, *args, **opts):
        
        if opts['prepend_main'] and opts['append_main']:
            raise CommandError("Please specify only one of --prepend-main-rules and --append-main-rules.")
        root_urlconf = getattr(settings, 'ROOT_URLCONF')
        
        d = opts['dir']
        if d is None:
            d = os.path.join(
                os.path.dirname(os.path.abspath(sys.modules[os.environ['DJANGO_SETTINGS_MODULE']].__file__)),
                'wpf_blogs'
            )
        else:
            d = os.path.abspath(d)

        if not os.path.isdir(d):
            if opts['force']:
                print "Creating destination folder '%s'" % d
                try:
                    os.mkdir(d)
                except Exception, e:
                    raise CommandError(e)
            else:
                raise CommandError("No such directory %s" % d)

        fname = os.path.join(d, '__init__.py')
        if not os.path.isfile(fname):
            if opts['force']:
                print "Creating missing '__init__.py' file in destination folder"
                try:
                    file(fname, 'w').write("# created by WP Frontman on %s\n" % datetime.datetime.now().isoformat())
                except Exception, e:
                    raise CommandError(e)
            else:
                print >>sys.stderr, "File '__init__.py' missing in destination folder, remember to create one"
            
        blogs = Blog.site.blogs
        print "%s blogs found" % len(blogs)
        if args:
            try:
                args = [int(a) for a in args]
            except (TypeError, ValueError):
                raise CommandError("Blog ids passed as arguments must be integers.")
            blogs = [b for b in blogs if b in args]
            print "%s blog%s kept" % (len(blogs), '' if len(blogs) == 1 else 's')
            
        print
        
        for b in blogs:
            blog = Blog.factory(b)
            fname = os.path.join(d, 'urls_%s.py' % blog.blog_id)
            if os.path.isfile(fname) and not opts['force']:
                print "Skipping blog id '%s', urlrules file already present." % blog.blog_id
                continue
            print "processing blog id %s (%s)" % (blog.blog_id, blog.blogname)
            rules, rules_dict = self.create_rules(
                blog, opts['strip_blog'], opts['feed_redirect'], opts['default_feed'],
                opts['search_base'], opts['search_view'], opts['additional_feeds'],
                opts['links_base']
            )
            buffer = ["'''WP Frontman urlrules for blog '%s', generated on %s'''\n" % (blog.blog_id, datetime.datetime.now().isoformat())]
            buffer.append("from django.conf.urls.defaults import *\n")
            if opts['prepend_main'] or opts['append_main']:
                buffer.append("from %s import urlpatterns as main_patterns\n" % root_urlconf)
            buffer.append("")
            buffer.append("urlpatterns = patterns('',")
            buffer.append("    " + ",\n    ".join(rules) % rules_dict)
            buffer.append(")\n\n")
            if opts['prepend_main']:
                buffer.append("urlpatterns = main_patterns + urlpatterns\n")
            elif opts['append_main']:
                buffer.append("urlpatterns += main_patterns\n")
            buffer = "\n".join(buffer)
            try:
                exec buffer in dict()
            except Exception, e:
                raise CommandError("Error parsing generated URL rules: %s" % e)
            file(fname, 'w').write(buffer)
            print "URL rules stored in '%s'." % fname
            print
            
    def create_rules(
        self, blog, strip_default=False, feed_redirect=False, default_feed=None,
        search_base=None, search_view=None, additional_feeds=None,
        links_base='links'
    ):
        
        ps = blog.permalink_ps
        if strip_default and blog.is_default and ps.startswith('blog\\/'):
            ps = ps[6:]
        append_slash = '/' if getattr(settings, 'APPEND_SLASH', False) else '/?'
        path = blog.urlrule_path
        
        rules = list()
        
        ### home ###
        rules.append("url('^%(path)s$', 'wp_frontman.views.index', name='wpf_index')")
        rules.append("url('^%(path)spage/(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.index', name='wpf_index')")
        rules.append("# url('^%(path)spage(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.index')")
        
        ### posts ###
        # files
        rules.append("url('^files/(?P<filepath>.*?)$', 'wp_frontman.views.media', name='wpf_media')")
        # regular post
        rules.append("url('^%(path)s%(ps)s%(append_slash)s$', 'wp_frontman.views.post', name='wpf_post')")
        
        ### archives, month ###
        rules.append("url('^%(path)s(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})%(append_slash)s$', 'wp_frontman.views.archives', name='wpf_archives')")
        rules.append("url('^%(path)s(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/page/(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.archives', name='wpf_archives')")
        rules.append("url('^%(path)s(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/page(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.archives')")
        ### archives, year ###
        rules.append("url('^%(path)s(?P<year>[0-9]{4})%(append_slash)s$', 'wp_frontman.views.archives', name='wpf_archives')")
        rules.append("url('^%(path)s(?P<year>[0-9]{4})/page/?(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.archives', name='wpf_archives')")
        ### author page ###
        rules.append("url('^%(path)s%(author_base)s/(?P<slug>[^/]+)%(append_slash)s$', 'wp_frontman.views.author', name='wpf_author')")
        rules.append("url('^%(path)s%(author_base)s/(?P<slug>[^/]+)/page/?(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.author', name='wpf_author')")
        ### category ###
        rules.append("url('^%(path)s%(category_base)s/(?P<slug>[^/]+)%(append_slash)s$', 'wp_frontman.views.category', name='wpf_category')")
        rules.append("url('^%(path)s%(category_base)s/(?P<slug>[^/]+)/page/?(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.category', name='wpf_category')")
        rules.append("#url('^%(path)s%(category_base)s/(?P<slug>[^/]+)/page(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.category')")
        if blog.site.categories_as_sets:
            rules.append("url('^%(path)s%(category_base)s/(?P<parents>(?:[^/]+/)+)(?P<slug>[^/]+)/page/(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.category', name='wpf_category')")
            rules.append("#url('^%(path)s%(category_base)s/(?P<parents>(?:[^/]+/)+)(?P<slug>[^/]+)/page(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.category')")
            rules.append("url('^%(path)s%(category_base)s/(?P<parents>(?:[^/]+/)+)(?P<slug>[^/]+)%(append_slash)s$', 'wp_frontman.views.category', name='wpf_category')")
        ### links ###
        rules.append("url('^%(path)s%(links_base)s/(?P<slug>[^/]+)%(append_slash)s$', 'wp_frontman.views.links', name='wpf_link_category')")
        rules.append("url('^%(path)s%(links_base)s/(?P<slug>[^/]+)/page/?(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.links', name='wpf_link_category')")
        rules.append("#url('^%(path)s%(links_base)s/(?P<slug>[^/]+)/page(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.links')")
        rules.append("url('^%(path)s%(links_base)s/(?P<parents>(?:[^/]+/)+)(?P<slug>[^/]+)/page/(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.links', name='wpf_link_category')")
        rules.append("#url('^%(path)s%(links_base)s/(?P<parents>(?:[^/]+/)+)(?P<slug>[^/]+)/page(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.links')")
        rules.append("url('^%(path)s%(links_base)s/(?P<parents>(?:[^/]+/)+)(?P<slug>[^/]+)%(append_slash)s$', 'wp_frontman.views.links', name='wpf_link_category')")
        ### search ###
        #url('^ricerca/(?P<q>.+)/(?P<month>[0-9]{6})/page/(?P<page>[0-9]+)/$', 'wpf_sphinx.views.search', name='wpf_sphinx'),
        #url('^ricerca/(?P<q>.+)/page/(?P<page>[0-9]+)/$', 'wpf_sphinx.views.search', name='wpf_sphinx'),
        #url('^ricerca/(?P<q>.+)/(?P<month>[0-9]{6})/$', 'wpf_sphinx.views.search', name='wpf_sphinx'),
        #url('^ricerca/(?P<q>.+)/$', 'wpf_sphinx.views.search', name='wpf_sphinx'),
        #url('^ricerca/$', 'wpf_sphinx.views.search', name='wpf_sphinx'),
        rules.append("url('^%(path)s%(search_base)s/(?P<q>.+)/(?P<month>[0-9]{6})/page/(?P<page>[0-9]+)%(append_slash)s$', '" + search_view + "', name='wpf_search')")
        rules.append("url('^%(path)s%(search_base)s/(?P<q>.+)/page/?(?P<page>[0-9]+)%(append_slash)s$', '" + search_view + "', name='wpf_search')")
        rules.append("url('^%(path)s%(search_base)s/(?P<q>.+)/(?P<month>[0-9]{6})%(append_slash)s$', '" + search_view + "', name='wpf_search')")
        rules.append("url('^%(path)s%(search_base)s%(append_slash)s$', '" + search_view + "', name='wpf_search')")
        rules.append("url('^%(path)s%(search_base)s/(?P<q>.+)%(append_slash)s$', '" + search_view + "', name='wpf_search')")
        ### tag ###
        rules.append("url('^%(path)s%(tag_base)s/(?P<slug>[^/]+)%(append_slash)s$', 'wp_frontman.views.tag', name='wpf_post_tag')")
        rules.append("url('^%(path)s%(tag_base)s/(?P<slug>[^/]+)/page/?(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.tag', name='wpf_post_tag')")
        ### pages ###
        # we use a custom middleware class for pages, we might want to add a rule at the bottom anyway so that we can use reverse though
        ### feeds ###
        # TODO: check comments feed urls, etc. // feed_check_redirect
        if feed_redirect:
            if default_feed:
                rules.append("url('^%(path)s" + default_feed + "$', 'wp_frontman.views.feed_check_redirect', name='wpf_feed')")
                rules.append("url('^%(path)sfeed%(append_slash)s$', 'wp_frontman.views.feed_check_redirect')")
            else:
                rules.append("url('^%(path)sfeed%(append_slash)s$', 'wp_frontman.views.feed_check_redirect', name='wpf_feed')")
            if additional_feeds:
                for f in additional_feeds.split(','):
                    rules.append("url('^%(path)s" + f + "$', 'wp_frontman.views.feed_check_redirect')")
            rules.append("url('^%(path)s(?:feed/)?(?:feed|rdf|rss|rss2|atom)%(append_slash)s$', 'wp_frontman.views.feed_check_redirect')")
            rules.append("url('^%(path)swp-(?:atom|feed|rdf|rss|rss2)\.php$', 'wp_frontman.views.feed_check_redirect')")
            rules.append("url('^%(path)sfeed_for_feedburner.xml$', 'wp_frontman.views.feed')")
            rules.append("url('^%(path)scomments/feed%(append_slash)s$', 'wp_frontman.views.feed_check_redirect', dict(feed_type='comments'), name='wpf_feed_comments')")
            rules.append("url('^%(path)scomments/(?:feed/)?(?P<feed_type>feed|rdf|rss|rss2|atom)%(append_slash)s$', 'wp_frontman.views.feed_check_redirect', dict(feed_type='comments'))")
            rules.append("url('^%(path)swp-commentsrss2.php$', 'wp_frontman.views.feed_check_redirect', dict(feed_type='comments'))")
            rules.append("url('^%(path)scomment_feed_for_feedburner.xml$', 'wp_frontman.views.feed_comments')")
        else:
            if default_feed:
                rules.append("url('^%(path)s" + default_feed + "$', 'wp_frontman.views.feed', name='wpf_feed')")
                rules.append("url('^%(path)sfeed%(append_slash)s$', 'wp_frontman.views.feed')")
            else:
                rules.append("url('^%(path)sfeed%(append_slash)s$', 'wp_frontman.views.feed', name='wpf_feed')")
            rules.append("url('^%(path)s(?:feed/)?(?:feed|rdf|rss|rss2|atom)%(append_slash)s$', 'wp_frontman.views.feed')")
            rules.append("url('^%(path)swp-(?:atom|feed|rdf|rss|rss2)\.php$', 'wp_frontman.views.feed')")
            rules.append("url('^%(path)scomments/feed%(append_slash)s$', 'wp_frontman.views.feed_comments', name='wpf_feed_comments')")
            rules.append("url('^%(path)scomments/(?:feed/)?(?P<feed_type>feed|rdf|rss|rss2|atom)%(append_slash)s$', 'wp_frontman.views.feed_comments')")
            rules.append("url('^%(path)swp-commentsrss2.php$', 'wp_frontman.views.feed_comments')")
        rules.append("url('^%(path)s%(author_base)s/(?P<nicename>[^/]+)/feed%(append_slash)s$', 'wp_frontman.views.feed_author', name='wpf_feed_author')")
        rules.append("url('^%(path)s%(author_base)s/(?P<nicename>[^/]+)(?:/feed)?/(?P<feed_type>feed|rdf|rss|rss2|atom)%(append_slash)s$', 'wp_frontman.views.feed_author')")
        
        rules.append("url('^%(path)s%(ps)s/feed%(append_slash)s$', 'wp_frontman.views.feed_post', name='wpf_feed_post')")
        rules.append("url('^%(path)s%(ps)s/(?:feed/)?(?P<feed_type>feed|rdf|rss|rss2|atom)%(append_slash)s$', 'wp_frontman.views.feed_post')")
        
        # trackback
        rules.append("url('^%(path)s%(ps)s/trackback%(append_slash)s$', 'wp_frontman.views.trackback', name='wpf_trackback')")
        # paged post
        rules.append("url('^%(path)s%(ps)s/page/(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.post', name='wpf_post')")
        # paged comments
        if getattr(blog, 'page_comments', False):
            rules.append("url('^%(path)s%(ps)s/comment-page-(?P<comment_page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.post', name='wpf_post_comments')")

        ### user registration, activation and login ###
        rules.append("# change the following according to your needs")
        rules.append("url('^users/registration%(append_slash)s$', 'wp_frontman.views.user_registration', name='wpf_user_registration')")
        rules.append("url('^users/welcome%(append_slash)s$', 'wp_frontman.views.user_registration_message', name='wpf_user_registration_message')")
        rules.append("url('^users/activation%(append_slash)s$', 'wp_frontman.views.user_activation', name='wpf_user_activation')")
        rules.append("url('^users/login%(append_slash)s$', 'wp_frontman.views.user_login', name='wpf_user_login')")
        rules.append("url('^users/logout%(append_slash)s$', 'wp_frontman.views.user_logout', name='wpf_user_logout')")
        rules.append("url('^users/profile%(append_slash)s$', 'wp_frontman.views.user_profile', name='wpf_user_profile')")
        rules.append("# dummy rules to have reverse url mapping work when using wp for users stuff")
        rules.append("#url('^wp-signup.php$', 'wp_frontman.views.user_registration', name='wpf_user_registration')")
        rules.append("#url('^wp-activate.php$', 'wp_frontman.views.user_activation', name='wpf_user_activation')")
        rules.append("#url('^wp-login.php$', 'wp_frontman.views.user_login', name='wpf_user_login')")
        rules.append("#url('^wp-login.php\?action=logout$', 'wp_frontman.views.user_login', name='wpf_user_login')")
        
        rules.append("#url('^%(path)s%(category_base)s/(?P<slug>[^/]+)(?:/feed)?/(?P<feed_type>feed|rdf|rss|rss2|atom)%(append_slash)s$', 'wp_frontman.views.feed_category', name='wpf_feed_category')")
        rules.append("#url('^%(path)s%(search_base)s/(?P<q>.+)(?:/feed)?/(?P<feed_type>feed|rdf|rss|rss2|atom)%(append_slash)s$', 'wp_frontman.views.feed_search', name='wpf_feed_search')")
        rules.append("#url('^%(path)s%(tag_base)s/(?P<slug>[^/]+)(?:/feed)?/(?P<feed_type>feed|rdf|rss|rss2|atom)%(append_slash)s$', 'wp_frontman.views.feed_tag', name='wpf_feed_tag')")
        
        ### custom taxonomies ###
        custom_taxonomies = blog.options.get('wp_frontman', dict()).get('custom_taxonomies', dict())
        if custom_taxonomies.get('enabled'):
            for k, v in custom_taxonomies.get('custom_taxonomies', dict()).items():
                slug = v.get('rewrite_slug')
                if slug:
                    rules.append("# '%s' custom taxonomy" % k)
                    rules.append("url('^%(path)s" + slug + "/(?P<slug>[^/]+)%(append_slash)s$', 'wp_frontman.views.taxonomy', dict(taxonomy='" + k + "'), name='wpf_" + k + "')")
                    rules.append("url('^%(path)s" + slug + "/(?P<slug>[^/]+)/page/?(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.taxonomy', dict(taxonomy='" + k + "'), name='wpf_" + k + "')")
                    if v['rewrite_hierarchical']:
                        rules.append("url('^%(path)s" + slug + "/(?P<parents>(?:[^/]+/)+)(?P<slug>[^/]+)/page/(?P<page>[0-9]+)%(append_slash)s$', 'wp_frontman.views.taxonomy', dict(taxonomy='" + k + "'), name='wpf_" + k + "')")
                        rules.append("url('^%(path)s" + slug + "/(?P<parents>(?:[^/]+/)+)(?P<slug>[^/]+)%(append_slash)s$', 'wp_frontman.views.taxonomy', dict(taxonomy='" + k + "'), name='wpf_" + k + "')")
        
        ### add attachment urls here if we need them ###
        
        rules_dict = dict(append_slash=append_slash, ps=ps, path=path)
        for k in ('author', 'category', 'links', 'search', 'tag'):
            v = locals().get('%s_base' % k) or getattr(blog, '%s_base' % k, k)
            if v is None or not v.strip():
                v = k
            if v.startswith('/'):
                v = v[1:]
            rules_dict['%s_base' % k] = v
                
        return rules, rules_dict
        
