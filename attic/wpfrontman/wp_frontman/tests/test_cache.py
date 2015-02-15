import unittest
import time

from django.core.cache import cache

from wp_frontman.cache import get_key, get_object_key, get_object_value, set_object_value, cache_timestamps


class DummyObject(object):
    
    def __init__(self, id):
        self.id = id

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)
    
    
class CacheTestCase(unittest.TestCase):
    
    def setUp(self):
        cache.clear()
    
    def testNotDummyCache(self):
        self.assertNotEqual(repr(type(cache)), "<class 'django.core.cache.backends.dummy.CacheClass'>")
    
    def testObjectCache(self):
        obj = DummyObject(5)
        obj_key = get_object_key(1, 'post', obj)
        self.assertTrue(not get_object_value(1, obj_key, ('post', 'comment_post')))
        set_object_value(obj_key, obj)
        self.assertEqual(get_object_value(1, obj_key, ('post', 'comment_post')), obj)
        cache_timestamps(1, 'comment', dict(id=1000, post_id=5), time.time())
        self.assertEqual(get_object_value(1, obj_key, ('post', 'comment_post')), None)
        