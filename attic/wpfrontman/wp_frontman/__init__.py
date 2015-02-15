from django.db import models


# mokeypatch blog.options.Options so that we can dynamically change db_table
# at runtime, ugly but less than other ways of doing this


def get_db_table(self):
    if not hasattr(self, '_db_table'):
        return self.__dict__['db_table']
    if not hasattr(self, 'db_table_arg'):
        return self._db_table
    arg = self.db_table_arg if not callable(self.db_table_arg) else self.db_table_arg()
    try:
        return self._db_table % arg
    except TypeError:
        return self._db_table
    
def set_db_table(self, value):
    self._db_table = value
    
def _get_join_cache(self):
    if not hasattr(self, 'db_table_arg'):
        return self._proxied_join_cache
    arg = self.db_table_arg if not callable(self.db_table_arg) else self.db_table_arg()
    return self._proxied_join_cache.setdefault(arg, {})
    
def _set_join_cache(self, v):
    self._proxied_join_cache = v

def setup_proxy(self, target):
    """
    Does the internal setup so that the current model is a proxy for
    "target".
    """
    self.pk = target._meta.pk
    self.proxy_for_model = target
    self._db_table = target._meta._db_table


models.options.Options.db_table = property(get_db_table, set_db_table)
models.options.Options._join_cache = property(_get_join_cache, _set_join_cache)
models.options.Options.setup_proxy = setup_proxy
models.options.DEFAULT_NAMES += ('db_table_arg',)
