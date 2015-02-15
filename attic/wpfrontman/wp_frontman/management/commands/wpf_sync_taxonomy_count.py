import os
import sys
import time

from optparse import make_option

from django.conf import settings
from django.db import connection
from django.core.management.base import BaseCommand, CommandError

from wp_frontman.blog import Blog


class Command(BaseCommand):
    
    usage = lambda s, sc: "Usage: ./manage.py %s [options] [blog_id_1 ... blog_id_n]" % sc
    help = "Syncs taxonomy post counts."
    requires_model_validation = False
    
    def handle(self, *args, **opts):
        
        verbosity = opts['verbosity']
        
        if args:
            try:
                args = [int(a) for a in args]
            except (TypeError, ValueError):
                raise CommandError("Invalid blog id in arguments")
            blogs = [b for b in Blog.get_blogs() if b.blog_id in args]
        else:
            blogs = Blog.get_blogs()

        cursor = connection.cursor()
        
        for blog in blogs:
            
            print "blog", blog.blog_id
            
            prefix=blog.db_prefix
            
            num = cursor.execute("""
                select
                    tt.parent, tp.slug, tt.term_taxonomy_id, t.slug, tt.taxonomy, tt.count
                from """ + prefix + """term_taxonomy tt
                inner join """ + prefix + """terms t on t.term_id=tt.term_id
                left join """ + prefix + """term_taxonomy ttp on ttp.term_taxonomy_id=tt.parent
                left join """ + prefix + """terms tp on tp.term_id=ttp.term_id
                order by tt.taxonomy, tp.slug, t.slug
            """)
            tt = cursor.fetchall()
            
            print num, "taxonomy instances found"
            
            num = cursor.execute("""
                select term_taxonomy_id, count(*)
                from """ + prefix + """term_relationships tr
                inner join """ + prefix + """posts p on p.ID=tr.object_id
                where p.post_type='post' and p.post_status='publish'
                group by term_taxonomy_id
            """)
            posts_tr = dict(cursor.fetchall())
            
            print num, "post relationships found"
            
            num = cursor.execute("""
                select term_taxonomy_id, count(*)
                from """ + prefix + """term_relationships tr
                inner join """ + prefix + """links l on l.link_id=tr.object_id
                where l.link_visible='Y'
                group by term_taxonomy_id
            """)
            links_tr = dict(cursor.fetchall())
            
            print num, "link relationships found"
            
            for parent_id, parent_slug, tt_id, slug, taxonomy, count in tt:
                if taxonomy in ('category', 'post_tag'):
                    new_count = posts_tr.get(tt_id, 0)
                else:
                    new_count = links_tr.get(tt_id, 0)
                #print "%s-%s>%s-%s old %s new %s" % (parent_id, parent_slug, tt_id, slug, count, new_count)
                if new_count != count:
                    print "%s %s-%s>%s-%s has count %s instead of %s, fixing" % (taxonomy, parent_id, parent_slug, tt_id, slug, count, new_count)
                cursor.execute("update " + prefix + "term_taxonomy set count=%s where term_taxonomy_id=%s", (new_count, tt_id))

            connection._commit()
            print
            
        
