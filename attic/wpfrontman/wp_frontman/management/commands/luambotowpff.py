import MySQLdb

from optparse import make_option
from collections import namedtuple

from django.db import connection
from django.db.utils import IntegrityError
from django.core.management.base import BaseCommand, CommandError

from wp_frontman.blog import Blog
from wp_frontman.models import Post, BaseComment, Term, TermTaxonomyBase, TermRelationshipBase


class Command(BaseCommand):
    
    option_list = BaseCommand.option_list + (
        make_option(
            "--source", type="str", dest="source", help="source database name"
        ),
        make_option(
            "--dest", type="str", dest="dest", help="destination database name"
        ),
        make_option(
            "--dest-blog-id", type="int", dest="blog_id", help="assign converted data to this blog_id"
        )
    )
    
    
    def echo(self, s):
        print
        print s
        print len(s) * '-'
    

    def convert_posts(self, source, dest, users):
        self.echo("Converting posts")
        table = Post._meta.db_table
        print "destination table", table
        num = dest.execute("delete from %s" % table)
        print "deleted %s posts" % num
        dest.execute("alter table %s auto_increment=1" % table)
        num = source.execute("select * from luambo_entry where status in ('A', 'P')")
        print num, "posts to convert"
        Entry = namedtuple('Entry',[f[0] for f in source.description])
        q = """
            insert into """ + table + """ (
                ID, post_author, post_date, post_date_gmt, post_content,
                post_title, post_excerpt, comment_status, ping_status,
                post_name, to_ping, pinged, post_modified, post_modified_gmt,
                post_content_filtered, comment_count
            ) values (
                %s, %s, %s, %s, %s,
                %s, '', 'closed', 'closed',
                %s, '', '', %s, %s,
                '', %s
            )
        """
        posts = list()
        for row in source.fetchall():
            e = Entry(*row)
            content = e.summary_source if not e.body_source else u"%s<!--more-->%s" % (e.summary_source, e.body_source)
            num = dest.execute(q, (
                e.id, users[e.author_id], e.published, e.published_utc, content,
                e.title,
                e.slug, e.updated, e.updated,
                e.comment_count
            ))
            posts.append(e.id)
        print len(posts), "posts converted"
        return posts
            
        
    def convert_pages(self, source, dest):
        self.echo("Converting pages")
        table = Post._meta.db_table
        print "destination table", table
        num = dest.execute("delete from %s where post_type='page'" % table)
        print "deleted %s pages" % num
        num = source.execute("select * from luambo_page")
        print num, "pages to convert"
        Page = namedtuple('Page',[f[0] for f in source.description])
        q = """
            insert into """ + table + """ (
                ID, post_author, post_date, post_date_gmt, post_content,
                post_title, post_excerpt, comment_status, ping_status,
                post_name, to_ping, pinged, post_modified, post_modified_gmt,
                post_content_filtered, comment_count, post_type
            ) values (
                NULL, 1, %s, %s, %s,
                %s, '', 'closed', 'closed',
                %s, '', '', %s, %s,
                '', 0, 'page'
            )
        """
        num = 0
        for row in source.fetchall():
            e = Page(*row)
            dest.execute(q, (
                e.published, e.published_utc, e.body_source,
                e.title,
                e.path.replace('/', ''), e.updated, e.updated_utc
            ))
            num += 1
        print num, "pages converted"


    def convert_comments(self, source, dest, users, posts):
        self.echo("Converting comments")
        table = BaseComment._meta.db_table
        print "destination table", table
        num = dest.execute("delete from %s" % table)
        print "deleted %s comments" % num
        dest.execute("alter table %s auto_increment=1" % table)
        num = source.execute("select * from luambo_comment where status='A'")
        print num, "comments to convert"
        Comment = namedtuple('Comment',[f[0] for f in source.description])
        q = """
            insert into """ + table + """ (
                comment_ID, comment_post_ID, comment_author, comment_author_email,
                comment_author_url, comment_author_IP, comment_date, comment_date_gmt,
                comment_content, comment_approved, comment_agent, comment_type, user_id
            ) values (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, '1', %s, %s, %s
            )
        """
        num = 0
        _posts = dict()
        for row in source.fetchall():
            c = Comment(*row)
            if not c.entry_id in posts:
                print "--- missing post id %s for comment %s" % (c.entry_id, c.id)
                continue
            dest.execute(q, (
                c.id, c.entry_id, c.username, c.email or '',
                c.url, c.ip_address, c.updated, c.updated_utc,
                c.body_source, c.user_agent, '' if c.comment_type == 'C' else 'trackback', users.get(c.author_id, "0")
            ))
            _posts[c.entry_id] = _posts.get(c.entry_id, 0) + 1
            num += 1
        for k, v in _posts.items():
            dest.execute("update wp_posts set comment_count=%s where ID=%s", (v, k))
        print num, "comments converted"
    

    def convert_users(self, source, dest):
        self.echo("Converting users")
        num = source.execute("select u.id, u.username, u.email from auth_user u inner join luambo_entry e on u.id=e.author_id where e.status='P' group by u.id")
        print num, "users found"
        users = dict()
        for _id, username, email in source.fetchall():
            if dest.execute("select ID from wp_users where user_email=%s", (email,)):
                users[_id] = dest.fetchone()[0]
                print "user", email, "matches user id", users[_id]
            else:
                dest.execute(
                    "insert into wp_users (user_login, user_nicename, user_email, display_name) values (%s, %s, %s, %s)",
                    (username, username, email, username)
                )
                users[_id] = dest.lastrowid
                print "user", email, "added as", dest.lastrowid
        return users
    
    
    def convert_terms(self, source, dest):
        self.echo("Converting categories and tags to terms")
        table = Term._meta.db_table
        print "destination table", table
        source.execute("select slug, name from luambo_category")
        _terms = source.fetchall()
        source.execute("select value, label from luambo_tag")
        _terms += source.fetchall()
        print len(_terms), "terms to convert"
        dest.execute("delete from %s" % table)
        dest.execute("alter table %s auto_increment=1" % table)
        terms = dict()
        for slug, name in _terms:
            try:
                dest.execute("insert into " + table + " (slug, name) values (%s, %s)", (slug, name))
            except IntegrityError:
                continue
            terms[slug] = dest.lastrowid
        print len(terms), "terms converted"
        return terms
    
    
    def convert_term_taxonomy(self, source, dest, terms):
        self.echo("Converting categories and tags to term taxonomy")
        table = TermTaxonomyBase._meta.db_table
        dest.execute("delete from %s" % table)
        dest.execute("alter table %s auto_increment=1" % table)
        source.execute("select * from luambo_category order by level")
        Category = namedtuple('Category',[f[0] for f in source.description])
        categories = dict()
        q = "insert into " + table + " (term_id, taxonomy, parent, description) values (%s, 'category', %s, '')"
        for row in source.fetchall():
            c = Category(*row)
            values = (terms[c.slug], 0 if not c.parent_id else categories[c.parent_id])
            dest.execute(q, values)
            categories[c.id] = dest.lastrowid
        source.execute("select * from luambo_tag")
        Tag = namedtuple('Tag',[f[0] for f in source.description])
        tags = dict()
        q = "insert into " + table + " (term_id, taxonomy, parent, description) values (%s, 'post_tag', 0, '')"
        for row in source.fetchall():
            t = Tag(*row)
            dest.execute(q, (terms[t.value],))
            tags[t.value] = dest.lastrowid
        return categories, tags
    
    
    def convert_term_relationships(self, source, dest, terms, categories, tags, posts):
        self.echo("Converting term relationships")
        table = TermRelationshipBase._meta.db_table
        dest.execute("delete from %s" % table)
        dest.execute("alter table %s auto_increment=1" % table)
        source.execute("select entry_id, category_id from luambo_entry_categories")
        tc = dict()
        for e, c in source.fetchall():
            if not e in posts:
                continue
            c_id = categories[c]
            dest.execute(
                "insert into " + table + " values (%s, %s, 0)",
                (e, c_id)
            )
            tc[c_id] = tc.get(c_id, 0) + 1
        source.execute("select entry_id, tag_id from luambo_entry_tags")
        for e, t in source.fetchall():
            if not e in posts:
                continue
            t_id = tags[t]
            dest.execute(
                "insert into " + table + " values (%s, %s, 0)",
                (e, t_id)
            )
            tc[t_id] = tc.get(t_id, 0) + 1
        table = TermTaxonomyBase._meta.db_table
        for k, v in tc.items():
            dest.execute("update " + table + " set count=%s where term_taxonomy_id=%s", (v, k))


    def handle(self, *args, **opts):
        
        if not args:
            op = 'all'
        else:
            op = args[0]
        
        source, dest = opts.get('source'), opts.get('dest')
        if not source or not dest:
            raise CommandError("Either the source or dest option is missing.")
            
        if dest != connection.settings_dict['NAME']:
            raise CommandError("The destination database '%s' is different from the one defined in settings.py." % dest)
            
        blog_id = opts.get('blog_id')
        if not blog_id:
            raise CommandError("No blog id specified")
        try:
            blog = Blog.factory(blog_id)
        except ValueError:
            raise CommandError("Invalid blog id %s" % blog_id)
            
        lconn = MySQLdb.connect(db=opts['source'], passwd=connection.settings_dict['PASSWORD'], charset='utf8', use_unicode=True)
        lcursor = lconn.cursor()
        cursor = connection.cursor()
        
        users = self.convert_users(lcursor, cursor)
        connection._commit()
        
        posts = self.convert_posts(lcursor, cursor, users)
        connection._commit()
            
        self.convert_pages(lcursor, cursor)
        connection._commit()

        self.convert_comments(lcursor, cursor, users, posts)
        connection._commit()
            
        terms = self.convert_terms(lcursor, cursor)
        categories, tags = self.convert_term_taxonomy(lcursor, cursor, terms)
        self.convert_term_relationships(lcursor, cursor, terms, categories, tags, posts)
        
        connection._commit()
            

    