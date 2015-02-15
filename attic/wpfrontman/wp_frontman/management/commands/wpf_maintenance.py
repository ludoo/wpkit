import os
import sys
import time
import subprocess
import select

from optparse import make_option

from django.conf import settings
from django.db import connection
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError

from wp_frontman.blog import Blog
from wp_frontman.cache import cache_timestamps


class Command(BaseCommand):
    
    option_list = BaseCommand.option_list + (
        make_option(
            "--delete-revisions", action="store_true", dest="revisions", default=False,
            help="delete revisions older than 48 hours"
        ),
        make_option(
            "--purge-cache", action="store_true", dest="cache", default=False,
            help="purge stale files from the cache"
        ),
        make_option(
            "--publish-future-posts", action="store_true", dest="future", default=False,
            help="publish posts that have been scheduled for past dates"
        ),
        make_option(
            "--wp-cron", action="store_true", dest="cron", default=False,
            help="run wp cron"
        ),
    )
    usage = lambda s, sc: "Usage: ./manage.py %s [options] [blog_id_1 ... blog_id_n]" % sc
    help = "Performs WP related management tasks."
    requires_model_validation = False
    
    def _message(self, m, double=None, line_char='-', verbosity=None):
        if verbosity == '0':
            return
        if double in ('pre', 'both'):
            print
        print m
        if line_char:
            print len(m) * line_char
        if double in ('post', 'both'):
            print

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
        
        if opts['cron']:
            self._message("Running wp-cron.php", 'pre', '=', verbosity=verbosity)
            wp_root = Blog.site.wp_root
            self._message("WP root '%s'" % wp_root, line_char='', verbosity=verbosity)
            if not wp_root:
                raise CommandError("No wp_root set for site")
            if not os.path.isdir(wp_root):
                raise CommandError("WP root '%s' is not a directory" % wp_root)
            if not os.access(wp_root, os.R_OK|os.X_OK):
                raise CommandError("No permissions to access WP root '%s'" % wp_root)
            wp_cron = os.path.join(wp_root, 'wp-cron.php')
            self._message("WP cron '%s'" % wp_cron, line_char='', verbosity=verbosity)
            if not os.path.isfile(wp_cron):
                raise CommandError("'%s' not found" % wp_cron)
            if not os.access(wp_cron, os.R_OK):
                raise CommandError("'%s' not readable" % wp_cron)
            cwd = os.getcwd()

            def _partial_read(proc, stout, stderr):
                while (select.select([proc.stdout],[],[],0)[0]!=[]):   
                    stdout += proc.stdout.read(1)
                while (select.select([proc.stderr],[],[],0)[0]!=[]):   
                    stderr += proc.stderr.read(1)

            try:
                os.chdir(wp_root)
                for b in blogs:
                    path = b.path or '/'
                    self._message("blog %s: setting domain as '%s' and path as '%s'" % (b.blog_id, b.domain, path), line_char='', verbosity=verbosity)
                    os.environ.update(dict(HTTP_HOST=b.domain, REQUEST_URI=path+'wp-cron.php'))
                    try:
                        p = subprocess.Popen(["php", "-f", "wp-cron.php"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        stdout, stderr = p.communicate()
                    except OSError, e:
                        raise CommandError("process error for blog %s, %s" % (b.blog_id, e))
                        continue
                    #stoud, stderr = '', ''
                    #while not p.poll():
                    #    _partial_read(p, stdout, stderr)
                        
                    #stdout = p.stdout.read()
                    if stdout:
                        print "output for blog %s:" % b.blog_id
                        print stdout
                    #stderr = p.stderr.read()
                    if stderr:
                        print "error for blog %s:" % b.blog_id
                        print stderr
                    retcode = p.returncode
                    if retcode:
                        print "non-zero returncode for blog %s: %s" % (b.blog_id, retcode)
                    if stdout or stderr or retcode:
                        print
            finally:
                os.chdir(cwd)
        
        if opts['revisions']:
            self._message("Removing revisions", 'pre', '=', verbosity=verbosity)
            for b in blogs:
                num = cursor.execute(
                    "delete from %sposts where post_type='revision' and post_status='inherit' and post_date <= now() - interval 2 day" % b.db_prefix
                )
                connection._commit()
                self._message("blog %s: %s old revisions removed" % (b.blog_id, num), line_char='', verbosity=verbosity)
            
        if opts['future']:
            self._message("Publishing future posts", 'pre', '=', verbosity=verbosity)
            for b in blogs:
                num = cursor.execute(
                    "select ID, post_date, post_author from %sposts where post_type='post' and post_status='future' and post_date <= now()" % b.db_prefix
                )
                message = "blog %s: no future posts found" % b.blog_id
                if num:
                    rows = cursor.fetchall()
                    num = cursor.execute(
                        "update %sposts set post_status='publish' where post_type='post' and post_status='future' and post_date <= now()" % b.db_prefix
                    )
                    if num:
                        timestamp = time.time()
                        for post_id, post_date, author_id in rows:
                            d = dict(id=post_id, date=post_date.strftime('%Y-%m-%d %H:%M:%S'), author_id=author_id)
                            cursor.execute("""
                                select t.term_taxonomy_id, t.taxonomy
                                from %sterm_relationships r
                                inner join %sterm_taxonomy t on t.term_taxonomy_id=r.term_taxonomy_id
                                where r.object_id=%%s
                            """ % (b.db_prefix, b.db_prefix), (post_id,))
                            d['taxonomy'] = dict((None, dict(zip(('id', 'taxonomy'), r))) for r in cursor.fetchall())
                            cache_timestamps(b.blog_id, 'post', d, timestamp)
                        message = "blog %s: %s future posts published" % (b.blog_id, num)
                    else:
                        message = "blog %s: no future posts published" % b.blog_id
                connection._commit()
                self._message(message, line_char='', verbosity=verbosity)
            
        if opts['cache']:
            
            cache_dir = getattr(cache, '_dir', None)
        
            if not cache_dir:
                raise CommandError("Cache backend %s does not support purging." % cache.__class__.__name__)
            if not os.path.isdir(cache_dir):
                raise CommandError("Cache directory %s not found." % cache_dir)
            if not os.access(cache_dir, os.R_OK|os.W_OK|os.R_OK):
                raise CommandError("Canno access cache directory %s." % cache_dir)
                
            self._message("Removing stale cache files", 'pre', '=', verbosity=verbosity)
            
            limit = time.time() - settings.CACHE_MIDDLEWARE_SECONDS
            checked = purged = 0
            
            for dirpath, dirnames, filenames in os.walk(cache_dir):
                for fname in filenames:
                    fname = os.path.join(dirpath, fname)
                    # use a stat-based approach so we won't need to read the files
                    checked += 1
                    if os.stat(fname).st_mtime < limit:
                        try:
                            os.unlink(fname)
                        except (IOError, OSError):
                            if verbosity:
                                print >>sys.stderr, "warning: error removing cache file", fname
                        else:
                            purged += 1
                try:
                    os.rmdir(dirpath)
                except OSError:
                    pass
            
            self._message("%s files checked, %s removed" % (checked, purged), line_char='', verbosity=verbosity)
        
        if opts['verbosity'] != '0':
            print
            
