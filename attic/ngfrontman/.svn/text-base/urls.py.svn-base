from django.conf import settings
from django.conf.urls.defaults import *


urlpatterns = patterns('',
    (r'^wpf_cache/', include('wp_frontman.cache.urls')),
)


if settings.DEBUG:
    # serve wordpress theme files
    urlpatterns += patterns('',
        (r'^(?P<path>wp-content/themes/.*)$', 'django.views.static.serve', dict(document_root=getattr(settings, 'WP_ROOT', ''), show_indexes=True)),
    )
    # serve wp-content/uploads files
    urlpatterns += patterns('',
        (r'^(?P<path>wp-content/uploads/.*)$', 'django.views.static.serve', dict(document_root=getattr(settings, 'WP_ROOT', ''), show_indexes=True)),
    )
    
