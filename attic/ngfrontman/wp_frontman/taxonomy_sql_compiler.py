# encoding: utf-8

from django.db.models.query import QuerySet
from django.db.models.sql.query import Query
from django.db.models.sql.compiler import SQLCompiler
from django.db import connections
from django.utils.importlib import import_module


class TaxonomyWhere(object):

    def __init__(self, table, alias):
        self.table = table
        self.alias = alias
    
    def as_sql(self, qn=None, connection=None):
        return " (%s.taxonomy is NULL or %s.taxonomy=%s.taxonomy) " % (
            self.alias, self.alias, self.table
            ), tuple()


class TaxonomyQuery(Query):
    
    _compiler_cache = dict()
    
    def clone(self, klass=None, memo=None, **kwargs):
        obj = super(TaxonomyQuery, self).clone(self.__class__, memo, **kwargs)
        return obj
    
    def get_compiler(self, using=None, connection=None):
        if using is None and connection is None:
            raise ValueError("Need either using or connection")
        if using:
            connection = connections[using]

        # Check that the compiler will be able to execute the query
        for alias, aggregate in self.aggregate_select.items():
            connection.ops.check_aggregate_support(aggregate)
            
        if connection.alias not in self._compiler_cache:
            mod = import_module(connection.ops.compiler_module)
            if not hasattr(mod, 'TaxonomySQLCompiler'):
                base_compiler = getattr(mod, self.compiler)

                class TaxonomySQLCompiler(base_compiler):
                    def pre_sql_setup(self):
                        super(TaxonomySQLCompiler, self).pre_sql_setup()
                        joined_taxonomies = list()
                        for table, column in self.query.related_select_cols:
                            if table != self.query.model._meta.db_table and column == 'taxonomy':
                                joined_taxonomies.append(table)
                        for alias, map in self.query.alias_map.items():
                            if not alias in joined_taxonomies:
                                continue
                            if map[0].endswith('_term_taxonomy') and not alias.endswith('_term_taxonomy'):
                                w = TaxonomyWhere(map[0], alias)
                                self.query.where.add(w, 'AND')
                                #break
                            
                setattr(mod, 'TaxonomySQLCompiler', TaxonomySQLCompiler)
            self._compiler_cache[connection.alias] = None

        return connection.ops.compiler('TaxonomySQLCompiler')(self, connection, using)

            
#class TaxonomyManagerMixin(object):
#    
#    def get_query_set(self):
#        return QuerySet(self.model, query=TaxonomyQuery(self.model), using=self.db)
    
    
"""
il queryset in __init__ riceve un'istanza di una classe derivata da django.db.sql.query
che ha fa override di get_compiler(), in modo che dopo aver ottenuto connection
e prima di chiedere il compiler a connection.ops.compiler()

* controlla nella propria cache se ha già il modulo, se non lo ha
* importa il modulo, dichiara la classe compiler che estende SQLCompiler del modulo
* chiede la classe iniettata a connection.ops.compiler()
"""
