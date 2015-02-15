# create the dummy package for blog urlconf modules if it does not exist
try:
    import wp_frontman.blog_urls
except ImportError:
    import sys
    from types import ModuleType
    sys.modules['wp_frontman.blog_urls'] = ModuleType('wp_frontman.blog_urls')
    