import os
import glob


__test__ = dict()


for f in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_*py')):
    name = os.path.basename(f)[:-3]
    mod = __import__(name, globals(), locals(), ['*'])
    for k in dir(mod):
        if k.endswith('TestCase'):
            locals()[k] = getattr(mod, k)
    __test__[name] = mod
