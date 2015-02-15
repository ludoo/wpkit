from django.db import models

from wp_frontman.taxonomy_sql_compiler import QuerySet, TaxonomyQuery


# TODO: move to the blog model as we need each blog's capabilities
#class UserManager(models.Manager):
#    
#    def users_can(self, capability):
#        roles = self.model.wp_blog.options['capabilities'].get(capability)
#        if roles is None:
#            raise ValueError("Unknown capability")
#        users = list()
#        for um in self.model.wp_blog.models.UserMeta.objects.filter(name='wp_capabilities').select_related('user'):
#            for role, active in um.parsed_value.items():
#                if active and role in roles:
#                    users.append(um.user)
#        return users
        

class TaxonomyManagerMixin(object):
    
    # values and valueslist qs have no select_related, should also work for the date qs but untested
    
    def get_query_set(self):
        return QuerySet(self.model, query=TaxonomyQuery(self.model), using=self.db)
    
    def categories(self):
        return self.get_query_set().filter(taxonomy='category')


def filtered_managed(func):
    func.filtered_manager = True
    return func


def filtered_manager_factory(name, kw, bases=None, default_orderby=None):
    if not hasattr(filtered_manager_factory, '_cache'):
        filtered_manager_factory._cache = dict()
    elif name in filtered_manager_factory._cache:
        return filtered_manager_factory._cache[name]
    bases = bases or (models.Manager,)
    cls = type(name, bases, {'__module__':__name__, 'use_for_related_fields':True})
    if not default_orderby:
        def get_query_set(self):
            return super(cls, self).get_query_set().filter(**kw)
    else:
        def get_query_set(self):
            return super(cls, self).get_query_set().filter(**kw).order_by(default_orderby)
    cls.get_query_set = get_query_set
    filtered_manager_factory._cache[name] = cls
    return cls


class FilteredQuerySetMixIn(object):
    
    def values(self, *fields):
        return self._clone(klass=self._valuesqueryset, setup=True, _fields=fields)
        
    def values_list(self, *fields, **kwargs):
        flat = kwargs.pop('flat', False)
        if kwargs:
            raise TypeError('Unexpected keyword arguments to values_list: %s' % (kwargs.keys(),))
        if flat and len(fields) > 1:
            raise TypeError("'flat' is not valid when values_list is called with more than one field.")
        return self._clone(klass=self._valueslistqueryset, setup=True, flat=flat, _fields=fields)

    def dates(self, field_name, kind, order='ASC'):
        """
        Returns a list of datetime objects representing all available dates for
        the given field_name, scoped to 'kind'.
        """
        assert kind in ("month", "year", "day"), "'kind' must be one of 'year', 'month' or 'day'."
        assert order in ('ASC', 'DESC'),  "'order' must be either 'ASC' or 'DESC'."
        return self._clone(klass=self._datequeryset, setup=True, _field_name=field_name, _kind=kind, _order=order)
    
    
class WPPrefetchRelatedQuerySetMixin(object):
    # I actually wrote this before seeing Diango's prefetch_related, go figure...
    
    def __init__(self, *args, **kw):
        super(WPPrefetchRelatedQuerySetMixin, self).__init__(*args, **kw)
        self._wp_prefetch_related = []

    def _clone(self, *args, **kw):
        obj = super(WPPrefetchRelatedQuerySetMixin, self)._clone(*args, **kw)
        obj._wp_prefetch_related = self._wp_prefetch_related
        return obj
    
    def wp_prefetch_related(self, rel_model, rel_field, attr_name=None, rel_related=None, **rel_filters):
        """
        Use a single query to prefetch related objects for a list of objects in a queryset
        
        Attributes:
        
        * rel_model   - the related model name
        
        * rel_field   - the field name of the foreign key pointing to this model
                        in the related model
        
        * attr_name   - the name of the attribute that holds the related objects,
                        defaults to 'wp_prefetched_' + rel_model.lower()
                      
        * rel_related - fields to set as select_related() for the related objects,
                        defaults to not using select_related() on the related queryset 
        
        Example:
        
        >>> blog.models.Post.objects.published().wp_prefetch_related(
            'BasePostRelTaxonomy', 'basepost', 'wp_prefetched_taxonomies',
            ['basepost', 'taxonomy', 'taxonomy__term', 'taxonomy__parent']
            )
        >>> 
        """
        obj = self._clone()
        obj._wp_prefetch_related.append((rel_model, rel_field, attr_name, rel_related, rel_filters))
        return obj
    
    def _fill_cache(self, num=None):
        super(WPPrefetchRelatedQuerySetMixin, self)._fill_cache(num)
        if not self._wp_prefetch_related or not self._result_cache:
            return
        # default attr_name if None
        rel_attrs = [r[2] or 'wp_prefetched_%s' % r[0].lower() for r in self._wp_prefetch_related]
        objects = dict()
        for obj in self._result_cache:
            for rel_attr in rel_attrs:
                setattr(obj, rel_attr, [])
            objects[obj.pk] = obj
        for rel_model, rel_field, attr_name, rel_related, rel_filters in self._wp_prefetch_related:
            obj_attr = rel_attrs.pop(0)
            filter = rel_filters
            filter['%s__pk__in' % rel_field] = objects.keys()
            qs = getattr(self.model.wp_blog.models, rel_model).objects.filter(**filter)
            # TODO: add another prefetch level for prefetched objects, eg
            #       prefetch attachments and prefetch their postmeta in one go (2 queries)
            if rel_related:
                qs = qs.select_related(*rel_related)
            for rel_obj in qs:
                getattr(objects[getattr(rel_obj, rel_field+'_id')], obj_attr).append(rel_obj)
        
            
class FilteredManagerMeta(type):
    
    
    def __new__(cls, name, bases, attrs):
        
        for b in bases:
            if getattr(b, '__metaclass__', None) is FilteredManagerMeta:
                return super(FilteredManagerMeta, cls).__new__(cls, name, bases, attrs)
        
        # find the methods defined in the manager class
        qs_attrs = dict((k, v) for k, v in attrs.items() if getattr(v, 'filtered_manager', False) or k == '__module__')
        sqs_attrs = qs_attrs.copy()
        
        # create the custom specialized queryset classes
        for c in (models.query.ValuesQuerySet, models.query.ValuesListQuerySet, models.query.DateQuerySet):
            qs_attrs['_%s' % c.__name__.lower()] = type(
                'Filtered%s' % c.__name__, (c,), sqs_attrs
            )
            
        # create the base queryset class
        qs = type('FilteredQuerySet', (FilteredQuerySetMixIn, WPPrefetchRelatedQuerySetMixin, models.query.QuerySet), qs_attrs)
        
        attrs['get_query_set'] = lambda s: qs(s.model, using=s._db)
        def debug_get_query_set(self):
            return qs(self.model, using=self._db)
        attrs['get_query_set'] = debug_get_query_set
        attrs['wp_prefetch_related'] = lambda s, *args, **kw: s.get_query_set().wp_prefetch_related(*args, **kw)
        attrs['wp_prefetch_related'].__doc__ = WPPrefetchRelatedQuerySetMixin.wp_prefetch_related.__doc__
        
        new_class = super(FilteredManagerMeta, cls).__new__(cls, name, bases, attrs)
        
        # return our manager
        return new_class

    
class BasePostManager(models.Manager):
    
    __metaclass__ = FilteredManagerMeta
    use_for_related_fields = True
    
    @filtered_managed
    def published(self):
        return self.filter(status='publish')

    @filtered_managed
    def posts(self):
        return self.filter(post_type='post')
    
    @filtered_managed
    def pages(self):
        return self.filter(post_type='page')
    
    @filtered_managed
    def mime_type(self, mime_type):
        return self.filter(mime_type=mime_type)
    
    @filtered_managed
    def mime_type_group(self, mime_group):
        return self.filter(mime_type__istartswith=mime_group)
    
    @filtered_managed
    def prefetch_taxonomies(self):
        """
        Prefetch taxonomies and all related objects for posts in this queryset.
        
        Existing taxonomies are put into a 'wp_prefetched_taxonomies' attribute
        for each object.
        """
        return self.wp_prefetch_related(
            'BasePostRelTaxonomy', 'basepost', 'wp_prefetched_taxonomies',
            ['basepost', 'taxonomy', 'taxonomy__term', 'taxonomy__parent']
        )

    @filtered_managed
    def prefetch_children(self):
        if not hasattr(self.model, 'parent_id'):
            return self
        return self.wp_prefetch_related('BasePost', 'parent', 'wp_prefetched_children')
        
    @filtered_managed
    def prefetch_attachments(self):
        if not hasattr(self.model.wp_blog.models, 'Attachment'):
            return self
        return self.wp_prefetch_related('BasePost', 'parent', 'wp_prefetched_attachments', post_type='attachment')
    
    @filtered_managed
    def prefetch_image_attachments(self):
        if not hasattr(self.model.wp_blog.models, 'Attachment'):
            return self
        return self.wp_prefetch_related('BasePost', 'parent', 'wp_prefetched_image_attachments', post_type='attachment', mime_type__startswith='image/')
        
    @filtered_managed
    def prefetch_postmeta(self):
        return self.wp_prefetch_related('PostMeta', 'post', 'wp_prefetched_postmeta')
    
    # TODO: add a method for featured_images so that we fetch everything
    #       in one go given a list of posts
    
#    @filtered_managed
#    def attachments(self):
#        return self.filter(post_type__in=('attachment', 'inherit'))
    

class LinkManager(models.Manager):
    
    __metaclass__ = FilteredManagerMeta
    use_for_related_fields = True
    
    @filtered_managed
    def visible(self):
        return self.filter(visible='Y')

    
class CommentManager(models.Manager):
    
    __metaclass__ = FilteredManagerMeta
    use_for_related_fields = True
    
    @filtered_managed
    def approved(self):
        return self.filter(approved='1')
    
    @filtered_managed
    def comments(self):
        return self.filter(comment_type='')
    
    @filtered_managed
    def trackbacks(self):
        return self.filter(comment_type='trackback')
    
    @filtered_managed
    def pingbacks(self):
        return self.filter(comment_type='pingback')
    
