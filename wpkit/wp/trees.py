try:
    from collections import OrderedDict
except ImportError:
    #from external.backports import OrderedDict
    from django.utils.datastructures import SortedDict as OrderedDict


def flatten_tree(d, level=0, max_level=None):
    for k, v in d.items():
        k.wpf_tree_level = level
        yield k
        if v and (max_level is None or max_level > level):
            for c in flatten_tree(v, level+1, max_level=max_level):
                yield c
    
    
def prune_tree(tree, filter_attr):
    for obj, children in tree.items():
        if children:
            prune_tree(children, filter_attr)
        if not children:
            value = getattr(obj, filter_attr, None)
            if not value:
                del tree[obj]


def get_set(tree, root_attr, root_value, attr='parent'):

    objects = dict()
    map = dict((obj.id, obj) for obj in tree)
    
    for obj in tree:
        _obj = obj
        while True:
            if getattr(_obj, root_attr) == root_value:
                objects[obj.id] = obj
                break
            parent = getattr(_obj, attr, None)
            if not parent:
                break
            if parent.id in objects:
                objects[obj.id] = obj
                break
            _obj = map.get(parent.id)
            if not _obj:
                break
    return objects.values()
    

def make_tree(tree, attr='parent'):
    """
    Return a flat list with a hierarchical representation of a tree.
    In WordPress we are dealing with small trees so we try to limit database
    access to a single query, and preserve the ordering set by the user.
    
    Input should be a flat list of objects with ancestors.
    The resulting list is ordered by each object's level, and its original ordering.
    
    >>> class N(object):
    ...     def __init__(self, id, parent=None): self.id, self.parent, self.orphaned = id, parent, False
    ...     def __repr__(self): return "%s:%s:%s" % (self.id, '' if not self.parent else self.parent.id, '*' if self.orphaned else '')
    ... 
    >>> n1, n2, n5 = N(1), N(2), N(5)
    >>> n4, n8, n7 = N(4, n1), N(8), N(7, n5)
    >>> n6 = N(6, n4)
    >>> # n10 is orphaned
    >>> tree = [n1, n6, n7, N(10, N(25)), N(9, n7), N(8, n7), n2, n5, N(11, n6), N(3, n4), n4]
    >>> [(o.wpf_tree_level, o) for o in flatten_tree(make_tree(tree))]
    [(0, 1::), (1, 4:1:), (2, 6:4:), (3, 11:6:), (2, 3:4:), (0, 10:25:), (0, 2::), (0, 5::), (1, 7:5:), (2, 9:7:), (2, 8:7:)]
    >>> [(o.wpf_tree_level, o) for o in flatten_tree(make_tree(tree), max_level=0)]
    [(0, 1::), (0, 10:25:), (0, 2::), (0, 5::)]
    >>> [(o.wpf_tree_level, o) for o in flatten_tree(make_tree(tree), max_level=1)]
    [(0, 1::), (1, 4:1:), (0, 10:25:), (0, 2::), (0, 5::), (1, 7:5:)]
    >>> 
    """
    
    root = OrderedDict()
    map = dict((obj.id, OrderedDict()) for obj in tree)
    
    for obj in tree:
        parent = getattr(obj, attr, None)
        if not parent:
            root[obj] = map[obj.id]
            continue
        if parent.id in map:
            map[parent.id][obj] = map[obj.id]
            continue
        # orphaned item, add it as a root object
        root[obj] = map[obj.id]
    
    return root

        
if __name__ == '__main__':
    import doctest
    doctest.testmod()
