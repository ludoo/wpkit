from django.apps import apps
from django.conf import settings
from django.db.models import Manager, QuerySet, Count
from django.db.models.query_utils import Q
from django.utils.lru_cache import lru_cache
from django.utils.functional import curry


app = apps.get_app_config('wpkit')

SITE_ID = app.wp_config.get('SITE_ID_CURRENT_SITE')
LRU_MAXSIZE = getattr(settings, 'WPKIT_LRU_MAXSIZE', None)


class SiteManager(Manager):
    
    @lru_cache(maxsize=LRU_MAXSIZE)
    def get_default(self):
        return self.get_queryset().get(id=SITE_ID)

    
class TaxonomyTermManager(Manager):
    
    use_for_related_fields = True
    
    def get_queryset(self):
        return super(TaxonomyTermManager, self).get_queryset().select_related('taxonomy')
    

class TaxonomyManager(Manager):
    
    use_for_related_fields = True
    
    def get_queryset(self):
        return super(TaxonomyManager, self).get_queryset().select_related('term')
    
    # TODO: create custom managers with a filter method for each taxonomy
    def categories(self):
        return self.filter(taxonomy='category')

    
class PostQuerySet(QuerySet):

    use_for_related_fields = True
    _wp_post_types_querysets = {}
    
    def as_manager(cls, post_types=None):
        if not post_types:
            return super(PostQuerySet, cls).as_manager()
        key = hash(tuple(post_types))
        if key not in cls._wp_post_types_querysets:
            cls._wp_post_types_querysets[key] = type(
                'PostQuerySet%s' % key, (cls,),
                dict(('%ss' % pt, curry(cls._post_type, post_type=pt)) for pt in post_types)
            )
        return Manager.from_queryset(
            cls._wp_post_types_querysets[key]
        )()

    as_manager.queryset_only = True
    as_manager = classmethod(as_manager)

    def _post_type(self, post_type):
        return self.filter(post_type=post_type)

    def published_posts(self):
        # TODO: add comments maybe?
        return self.filter(
            status='publish', post_type='post'
        ).prefetch_related(
            'taxonomies_rel'
        )
    
    def monthly_archives(self):
        return self.extra(
            {'date':"cast(date_format(post_date, '%%Y-%%m-01') as date)"}
        ).values('date').annotate(num_posts=Count('id'))
        
    def yearly_archives(self):
        return self.extra(
            {'date':"cast(date_format(post_date, '%%Y-01-01') as date)"}
        ).values('date').annotate(num_posts=Count('id'))

    def published(self):
        return self.filter(status='publish')

    def future(self):
        return self.filter(status='future')

    def draft(self):
        return self.filter(status='draft')

    def pending(self):
        return self.filter(status='pending')

    def private(self):
        return self.filter(status='private')

    def trash(self):
        return self.filter(status='trash')

    def auto_draft(self):
        return self.filter(status='auto-draft')

    def inherit(self):
        return self.filter(status='inherit')

    
class CommentQuerySet(QuerySet):
    
    use_for_related_fields = True

    def comments(self):
        return self.filter(comment_type='')
    
    def trackbacks(self):
        return self.filter(comment_type='trackback')
    
    def pingbacks(self):
        return self.filter(comment_type='pingback')
    
    def approved(self):
        return self.filter(approved='1')
