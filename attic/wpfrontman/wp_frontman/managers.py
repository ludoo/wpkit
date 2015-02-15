from urllib import quote

from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import set_urlconf, get_resolver, Resolver404
from django.db import models

from wp_frontman.blog import Blog
from wp_frontman.taxonomy_sql_compiler import QuerySet, TaxonomyQuery


WPF_CATEGORIES_AS_SETS = Blog.site.categories_as_sets


class DuplicatePermalink(Exception): pass


class TaxonomyManagerMixin(object):
    
    # values and valueslist qs have no select_related, should also work for the date qs but untested
    
    def get_query_set(self):
        return QuerySet(self.model, query=TaxonomyQuery(self.model), using=self.db)


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
        qs = type('FilteredQuerySet', (FilteredQuerySetMixIn, models.query.QuerySet), qs_attrs)
        
        # attrs['get_query_set'] = attrs.get('get_query_set', lambda s: qs(s.model, using=s._db))
        attrs['get_query_set'] = lambda s: qs(s.model, using=s._db)
        
        new_class = super(FilteredManagerMeta, cls).__new__(cls, name, bases, attrs)
        
        # return our manager
        return new_class

    
class PublishedPostManager(models.Manager):
    
    __metaclass__ = FilteredManagerMeta
    use_for_related_fields = True
    
    @filtered_managed
    def published(self):
        return self.filter(status='publish')


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
    
#    @filtered_managed
#    def attachments(self):
#        return self.filter(post_type__in=('attachment', 'inherit'))
    

class PostManager(BasePostManager):
    
    def get_query_set(self):
        return super(PostManager, self).get_query_set().filter(post_type='post')

    def get_from_path(self, path):
        resolver = get_resolver(Blog.get_active().urlconf)
        try:
            view, args, kw = resolver.resolve(path)
        except Resolver404, e:
            raise ObjectDoesNotExist("Post for path '%s' not found." % path)
        return self.get_from_keywords(kw)
    
    def get_from_keywords(self, kw):
        post = None
        post_id = kw.get('id')
        if post_id:
            # we have a post id, we don't need anything else
            try:
                post_id = int(post_id)
                post = self.get(id=post_id)
            except (TypeError, ValueError):
                pass
            #except ObjectDoesNotExist:
            #    return
            else:
                category = kw.get('category')
                if category and WPF_CATEGORIES_AS_SETS and post.permalink_tokens.get('category'):
                    if category != post.permalink_tokens.get('category'):
                        raise DuplicatePermalink(post.get_absolute_url())
                if 'slug' in kw and kw['slug'] != post.slug:
                    raise DuplicatePermalink(post.get_absolute_url())
                return post
        slug = kw.get('slug')
        if not slug:
            raise ObjectDoesNotExist("Post with slug '%s' not found." % slug)
        permalink_filters = self.model.get_permalink_filters(**kw)
        if not permalink_filters:
            raise ObjectDoesNotExist("No permalink filters for post")
        posts = None
        for _slug in set([None, quote(slug.encode('utf-8')).lower(), quote(slug.encode('utf-8'))]):
            if _slug:
                permalink_filters['slug'] = _slug
            posts = self.filter(status__in=('publish', 'future')).select_related('author').filter(**permalink_filters)
            if posts:
                break
        if not posts:
            raise ObjectDoesNotExist("Post not found.")
        return posts[0]
    

class PageManager(BasePostManager):
    
    def get_query_set(self):
        return super(PageManager, self).get_query_set().filter(post_type='page')

    
class LinkManager(models.Manager):
    
    __metaclass__ = FilteredManagerMeta
    use_for_related_fields = True
    
    @filtered_managed
    def visible(self):
        return self.filter(visible='Y')

    
class BaseCommentManager(models.Manager):
    
    __metaclass__ = FilteredManagerMeta
    use_for_related_fields = True
    
    @filtered_managed
    def approved(self):
        return self.filter(approved='1')

    @filtered_managed
    def posts(self):
        return self.filter(base_post__post_type='post')
    
    @filtered_managed
    def pages(self):
        return self.filter(base_post__post_type='page')
    
