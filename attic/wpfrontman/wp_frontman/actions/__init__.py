import os
import glob
import warnings


def register_actions():

    basedir = os.path.dirname(os.path.abspath(__file__))
    action_names = [os.path.basename(f)[:-3] for f in glob.glob(os.path.join(basedir, '[a-z]*.py'))]
    
    for name in action_names:
        mod_name = "wp_frontman.actions.%s" % name
        try:
            mod = __import__(mod_name, fromlist=(name,), level=1)
        except ImportError, e:
            warnings.warn("Cannot import action %s: %s" % (mod_name, e))
            continue
        mod_func = getattr(mod, 'register', None)
        if mod_func and callable(mod_func):
            mod_func()
        else:
            warnings.warn("Action %s invalid: got %s when looking for register() in %s" % (mod_name, mod_func, mod))
    

