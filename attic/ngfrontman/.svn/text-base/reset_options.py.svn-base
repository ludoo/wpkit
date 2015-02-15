#!/usr/bin/env python

import sys
import os

basepath = os.path.sep.join(os.path.abspath(os.path.dirname(__file__)).split(os.path.sep)[:-1])
sys.path.append(basepath)
os.environ['DJANGO_SETTINGS_MODULE'] = 'ngfrontman.settings'

from django.conf import settings
from django.db import connections


settings.DATABASES['wpf_multi'] = settings.DATABASES['default'].copy()
settings.DATABASES['wpf_multi']['NAME'] = 'wpf_multi'


print "%s rows removed from default database" % connections['default'].cursor().execute("delete from wp_options where option_name like 'wp_frontman%%'")
connections['default']._commit()

conn = connections['wpf_multi']
cursor = conn.cursor()

print "%s rows removed from multi database sitemeta" % cursor.execute("delete from wp_sitemeta where meta_key='wp_frontman'")
conn._commit()
cursor.execute("select blog_id from wp_blogs")
for row in cursor.fetchall():
    blog_id = str(row[0])
    print "%s rows removed from multi database for blog %s" % (
        cursor.execute("delete from %s_options where option_name='wp_frontman'" % ('wp' if blog_id=='1' else 'wp_'+blog_id)),
        blog_id
    )
conn._commit()
