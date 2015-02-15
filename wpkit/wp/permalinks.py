import re
import logging


TOKENS = {
    'year': '[0-9]{4}',
    'monthnum': '[0-9]{1,2}',
    'day': '[0-9]{1,2}',
    'hour': '[0-9]{1,2}',
    'minute': '[0-9]{1,2}',
    'second': '[0-9]{1,2}',
    'postname': '[^/]+',
    'post_id': '[0-9]+',
    'category': '.+?',
    'tag': '.+?',
    'author': '[^/]+',
    'pagename': '[^/]+?',
    'search': '.+',
}
    
MAP = {
    'monthnum': 'month',
    'postname': 'slug',
    'post_id': 'id',
    'search': 'q',
}

RE = re.compile(r'%([a-z_]+)%')

BASES = {
    'category': 'category',
    'tag': 'tag',
    'pagination': 'page',
    'author': 'author',
    'search': 'search'
}

logger = logging.getLogger('wpkit.wp.permalinks')


def process_permalink(ps):
    
    if not ps:
        raise ValueError("Permalink structure cannot be empty or null")
    
    base = ps
        
    if base.startswith('/index.php'):
        base = base[10:]

    if base.startswith('/'):
        base = base[1:]

    start = 0
    tokens = []
    rule_tokens = []
    scanner = RE.scanner(base)
    
    while True:
        m = scanner.search()
        if not m:
            break
        rule_tokens.append(base[start:m.start()])
        tokens.append(MAP.get(m.group(1), m.group(1)))
        rule_tokens.append('(?P<%s>%s)' % (tokens[-1], TOKENS[m.group(1)]))
        start = m.end()
    
    rule_tokens.append(base[start:])
    
    rule = ''.join(rule_tokens)
    
    # TODO: rule should end with a trailing slash, unless it's a file-like pattern
    if rule.endswith('/'):
        rule = rule[:-1]

    return tuple(tokens), rule


def wp_urlpatterns(path, ps_pattern, blog_bases):
    """
    path        the path derived from the home URL
    ps_pattern  the permalink_structure url pattern returned from process_permalink()
    bases       a dictionary of object class bases from the blog options
    
    return a list of urlpatterns
    """
    
    path = '/'.join(t for t in path.split('/') if t)
    if path:
        path += '/'
    
    bases = BASES.copy()
    bases.update(dict((k, v) for k, v in blog_bases.items() if v))
    
    patterns = []
    
    #ps_pattern = ps_pattern or process_permalink(permalink_structure)[1]
    
    paging_suffix = bases['pagination'] + '/(?P<page>[0-9]+)/'
    #comment_paging_suffix = 'comment-page-(?P<page>[0-9]+)/'
    taxonomy_single = r'^%s%%s/(?P<slug>[^/]+)' % path
    taxonomy_hierarchical = r'^%s%%s/(?P<hierarchy>(?:[^/]+/)+)(?P<slug>[^/]+)' % path
    
    # home
    patterns.append((
        r'^%s$' % path, 'wpkit.views.index', dict(), 'wpkit_index'
    ))
    patterns.append((
        r'^%s%s$' % (path, paging_suffix), 'wpkit.views.index', dict(), 'wpkit_index'
    ))
    
    # favicon and robots
    patterns.append((
        r'^favicon.ico$', 'wpkit.views.favicon', dict(), 'wpkit_favicon'
    ))
    patterns.append((
        r'^robots.txt$', 'wpkit.views.robots', dict(), 'wpkit_robots'
    ))
    
    # feed
    patterns.append((
        r'^%sfeed/$' % path, 'wpkit.views.feed', dict(), 'wpkit_feed'
    ))
    patterns.append((
        r'^%scomments/feed/$' % path, 'wpkit.views.feed_comments', dict(), 'wpkit_feed_comments'
    ))
    
    # files
    patterns.append((
        r'^%sfiles/(?P<filepath>.*?)$' % path, 'wpkit.views.media', dict(), 'wpkit_media'
    ))
    
    # posts
    patterns.append((
        '^%s%s/$' % (path, ps_pattern), 'wpkit.views.post', dict(), 'wpkit_post'
    ))
    
    # attachments
    patterns.append((
        '^%s%s/attachment/(?P<attachment_slug>[^/]+)/$' % (path, ps_pattern),
        'wpkit.views.post', dict(), 'wpkit_attachment'
    ))
    
    # pages
    patterns.append((
        '^%s(?P<slug>[^/]+)/$' % path,
        'wpkit.views.post', dict(), 'wpkit_page'
    ))

    # taxonomies: categories
    patterns.append((
        (taxonomy_single % bases['category']) + '/' + paging_suffix + '$',
        'wpkit.views.taxonomy', dict(taxonomy='category'), 'wpkit_category'
    ))
    patterns.append((
        (taxonomy_single % bases['category']) + '/$',
        'wpkit.views.taxonomy', dict(taxonomy='category'), 'wpkit_category'
    ))
    patterns.append((
        (taxonomy_hierarchical % bases['category']) + '/' + paging_suffix + '$',
        'wpkit.views.taxonomy', dict(taxonomy='category'), 'wpkit_category'
    ))
    patterns.append((
        (taxonomy_hierarchical % bases['category']) + '/$',
        'wpkit.views.taxonomy', dict(taxonomy='category'), 'wpkit_category'
    ))

    # taxonomies: tag
    patterns.append((
        (taxonomy_single % bases['tag']) + '/$',
        'wpkit.views.taxonomy', dict(taxonomy='post_tag'), 'wpkit_post_tag'
    ))
    patterns.append((
        (taxonomy_single % bases['tag']) + '/' + paging_suffix + '$',
        'wpkit.views.taxonomy', dict(taxonomy='post_tag'), 'wpkit_post_tag'
    ))

    # taxonomies: post formats
    patterns.append((
        r'^%stype/(?P<slug>[^/]+)/$' % path,
        'wpkit.views.taxonomy', dict(taxonomy='post_format'), 'wpkit_post_format'
    ))
    patterns.append((
        r'^%stype/(?P<slug>[^/]+)/%s$' % (path, paging_suffix),
        'wpkit.views.taxonomy', dict(taxonomy='post_format'), 'wpkit_post_format'
    ))
    
    # TODO: custom taxonomies
    """
    # custom taxonomies
    for k, v in self.options['wpkit']['custom_taxonomies'].items():
        patterns.append(((taxonomy_single % v['rewrite_slug']) + '/$', 'wpkit.views.taxonomy', dict(taxonomy=k), 'wpkit_' + k))
        patterns.append(((taxonomy_single % v['rewrite_slug']) + '/' + paging_suffix + '$', 'wpkit.views.taxonomy', dict(taxonomy=k), 'wpkit_' + k))
        if v['rewrite_hierarchical']:
            patterns.append(((taxonomy_hierarchical % v['rewrite_slug']) + '/$', 'wpkit.views.taxonomy', dict(taxonomy=k), 'wpkit_' + k))
            patterns.append(((taxonomy_hierarchical % v['rewrite_slug']) + '/' + paging_suffix + '$', 'wpkit.views.taxonomy', dict(taxonomy=k), 'wpkit_' + k))
    """
    
    # archives
    patterns.append((
        r'^%s(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/$' % path,
        'wpkit.views.archive', dict(), 'wpkit_archive'
    ))
    patterns.append((
        r'^%s(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/%s$' % (path, paging_suffix),
        'wpkit.views.archive', dict(), 'wpkit_archive'
    ))
    patterns.append((
        r'^%s(?P<year>[0-9]{4})/$' % path,
        'wpkit.views.archive', dict(), 'wpkit_archive'
    ))
    patterns.append((
        r'^%s(?P<year>[0-9]{4})/%s$' % (path, paging_suffix),
        'wpkit.views.archive', dict(), 'wpkit_archive'
    ))
        
    # author
    patterns.append((
        '^%s%s/(?P<slug>[^/]+)/$' % (path, bases['author']),
        'wpkit.views.author', dict(), 'wpkit_author'
    ))
    patterns.append((
        '^%s%s/(?P<slug>[^/]+)/%s$' % (path, bases['author'], paging_suffix),
        'wpkit.views.author', dict(), 'wpkit_author'
    ))
    
    # search
    patterns.append((
        '^%s%s/$' % (path, bases['search']),
        'wpkit.views.search', dict(), 'wpkit_search'
    ))
    patterns.append((
        '^%s%s/(?P<q>.+)/$' % (path, bases['search']),
        'wpkit.views.search', dict(), 'wpkit_search'
    ))
    patterns.append((
        '^%s%s/(?P<q>.+)/%s$' % (path, bases['search'], paging_suffix),
        'wpkit.views.search', dict(), 'wpkit_search'
    ))

    return patterns
    
    
"""
blog option permalink_structure post/archives URLs
blog option %_meta              prefix for % object

            'author_base'               => 'author',
            'search_base'               => 'search',
            'comments_base'             => 'comments',
            'pagination_base'           => 'page',
            'feed_base'                 => 'feed',
            'category_base'             => 'category',
            'tag_base'                  => 'tag'

"""