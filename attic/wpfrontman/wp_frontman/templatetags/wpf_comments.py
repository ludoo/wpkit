from django import template
from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse

from wp_frontman.blog import Blog
from wp_frontman.lib.utils import make_tree, OrderedDict


register = template.Library()


class WPFrontmanComments(template.Node):
    
    def __init__(self, post, page, filter):
        self.post = template.Variable(post)
        self.page = None if not page else template.Variable(page)
        self.filter = filter
        
    def render(self, context):
        
        blog = Blog.get_active()
        page = None if not self.page else self.page.resolve(context)
        post = self.post.resolve(context)
        
        if post.comment_count == 0:
            context['comments'] = list()
            context['page'] = page
            context['page_previous'] =  context['page_previous_url'] = None
            context['page_next'] =  context['page_next_url'] = None
            return ''
        
        try:
            page = int(page)
        except (TypeError, ValueError):
            page = None
            
        # define our base queryset
        qs = post.basecomment_set.approved() # add .select_related('parent') later
        
        if self.filter:
            qs = qs.filter(self.filter)

        page_next = page_previous = page_previous_url = page_next_url = None

        if not blog.page_comments or post.comment_count <= blog.comments_per_page:
            # set the correct ordering, we have all we need
            if blog.comment_order == 'asc':
                qs = qs.order_by('date', 'id')
            else:
                qs = qs.order_by('-date', '-id')
            # we have all we need to display comments
            if blog.thread_comments:
                comments = make_tree(list(qs.select_related('parent')))
            else:
                comments = list(qs)
        else:
            
            # set ascending order for pagination
            qs = qs.order_by('date', 'id')
            
            # if we are using threaded comments, we need a count of the toplevel ones
            if blog.thread_comments:
                num = qs.filter(parent__isnull=True).count()
            elif self.filter:
                num = qs.count()
            else:
                num = post.comment_count
                
            rest = num % blog.comments_per_page
            ordering_scheme = blog.comment_order + blog.default_comments_page
            
            if ordering_scheme in ('ascfirst', 'desclast'):
                default_page = 'first'
            else:
                default_page = 'last'
            
            # are we looking at the default page?
            if page is None:
                # find out if we need the first or last page
                # then set navigation variables
                if default_page == 'first':
                    # we need to show the first complete page
                    start, end = 0, blog.comments_per_page
                else:
                    if rest:
                        # we need to show the last page fragment
                        start, end = num - rest, num
                    else:
                        # we need to show the last complete page
                        start, end = num - blog.comments_per_page, num
            else:
                # the page number always reflects ascending order
                start = (page - 1) * blog.comments_per_page
                end = start + blog.comments_per_page
                    
            # get the comments
            if blog.thread_comments:
                # get the toplevel comments then build the tree
                top_ids = list(r[0] for r in qs.filter(parent__isnull=True).values_list('id')[start:end])
                comment_ids = dict(r for r in qs.filter(id__gte=min(top_ids), parent__id__isnull=False).order_by('id').values_list('id', 'parent_id'))
                for k, v in comment_ids.items():
                    while v:
                        if v in top_ids:
                            top_ids.append(k)
                            break
                        v = comment_ids.get(v)
                comments = make_tree(qs.filter(id__in=top_ids).select_related('parent'))
                if blog.comment_order == 'desc':
                    root = OrderedDict()
                    for k in sorted(comments, key=lambda c: (c.date, c.id), reverse=True):
                        root[k] = comments[k]
                    comments = root
            else:
                comments = qs[start:end]
                if blog.comment_order == 'desc':
                    comments = sorted(comments, key=lambda c: (c.date, c.id), reverse=True)

            # set the pagination variables
            if hasattr(post, 'permalink_tokens'):
                pattern_name = 'wpf_post_comments'
                pattern_kw = post.permalink_tokens
            else:
                pattern_name = 'wpf_page_comments'
                pattern_kw = dict(slug=post.slug)

            num_pages = num / blog.comments_per_page
            if rest:
                num_pages += 1
                
            #print "determining page numbers for", page, "comments per page", blog.comments_per_page, "comments", num, "number of pages", num_pages, "rest", rest, "scheme", ordering_scheme
            
            if page is None:
                # default page
                if ordering_scheme == 'ascfirst':
                    page_next = 2
                elif ordering_scheme == 'asclast':
                    page_previous = num_pages - 1
                elif ordering_scheme == 'desclast':
                    # dumb scheme
                    page_previous = 2
                else: # descfirst
                    page_next = num_pages - 1
                if page_previous:
                    pattern_kw['comment_page'] = page_previous
                    page_previous_url = reverse(pattern_name, kwargs=pattern_kw)
                if page_next:
                    pattern_kw['comment_page'] = page_next
                    page_next_url = reverse(pattern_name, kwargs=pattern_kw)
            else:
                # regular pages
                if blog.comment_order == 'asc':
                    if page > 1:
                        page_previous = page - 1
                    if page < num_pages:
                        page_next = page + 1
                    # check if we are adjacent to a default page
                    if blog.default_comments_page == 'first':
                        if page == 2:
                            page_previous = None
                            page_previous_url = post.get_absolute_url()
                    elif page == num_pages - 1:
                        page_next = None
                        page_next_url = post.get_absolute_url()
                else:
                    if page > 1:
                        page_next = page - 1
                    if page < num_pages:
                        page_previous = page + 1
                    # check if we are adjacent to a default page
                    if default_comments_page == 'last':
                        if page == 2:
                            page_next = None
                            page_next_url = post.get_absolute_url()
                    elif page == num_pages - 1:
                        page_previous = None
                        page_previous_url = post.get_absolute_url()
                if page_previous and not page_previous_url:
                    pattern_kw['comment_page'] = page_previous
                    page_previous_url = reverse(pattern_name, kwargs=pattern_kw)
                if page_next and not page_next_url:
                    pattern_kw['comment_page'] = page_next
                    page_next_url = reverse(pattern_name, kwargs=pattern_kw)
                    
        # set context variables
        context['comments'] = comments
        context['page'] = page
        context['page_previous'] = page_previous
        context['page_previous_url'] = page_previous_url
        context['page_next'] = page_next
        context['page_next_url'] = page_next_url
        return ''


@register.tag
def wpfcomments(parser, token):
    
    args = token.contents.split()
    
    if len(args) < 2:
        raise template.TemplateSyntaxError("wpf_comments needs at least a post")
    
    args = args[1:]
    
    post = args.pop(0)

    page = filter = None
    
    if args:
        page = args.pop(0)
    if args:
        filter = args.pop(0)

    if args:
        raise template.TemplateSyntaxError("too many arguments for wpf_comments")

    #template_fragment = parser.parse(('endwpfcomments',))
        
    #parser.delete_first_token()

    return WPFrontmanComments(post, page, filter)
