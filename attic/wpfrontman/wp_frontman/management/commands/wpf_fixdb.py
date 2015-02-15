from optparse import make_option
from MySQLdb import OperationalError

from django.conf import settings
from django.db import connection, DatabaseError
from django.core.management.base import BaseCommand, CommandError

from wp_frontman.lib.introspection import MySQLIntrospection
from wp_frontman.blog import Blog, DB_PREFIX


class Command(BaseCommand):
    
    option_list = BaseCommand.option_list + (
        make_option(
            "--force", action="store_true", dest="force", default=False,
            help="apply or revert changes instead of simply showing what would be done"
        ),
        make_option(
            "--revert", action="store_true", dest="revert", default=False,
            help="revert any change previously applied"
        ),
        make_option(
            "--myisam", action="store_true", dest="myisam", default=False,
            help="convert tables to MyISAM when reverting"
        ),
    )
    
    def handle(self, *args, **opts):
        
        db = MySQLIntrospection(connection.settings_dict['NAME'], connection.cursor())
        self.cursor = db.cursor

        Blog.default_active()
        
        self.dummy = not opts['force']
        self.revert = opts['revert']
        
        self._message("%s changes to tables in database %s (dummy %s)" % ('Applying' if not self.revert else 'Reverting', db.db, self.dummy), True, '=')
        
        self.justify = 50 #max(len(t) for t in db.tables.keys()) + 1
        
        if not self.revert:
            self._innodb(db)
            self._user_tables(db)
            for b in Blog.site.blogs:
                self._message("Blog id %s" % b)
                print
                Blog.factory(b)
                self._posts_tables(db)
                self._terms_table(db)
                self._term_taxonomy_tables(db)
                self._comments_tables(db)
        else:
            # reverse order
            for b in Blog.site.blogs:
                self._message("Blog id %s" % b)
                print
                Blog.factory(b)
                self._comments_tables(db)
                self._term_taxonomy_tables(db)
                self._terms_table(db)
                self._posts_tables(db)
            self._user_tables(db)
            if opts['myisam']:
                self._innodb(db)
        
        connection._commit()

    def _user_tables(self, db):
        u = db.tables['%susers' % DB_PREFIX]
        um = db.tables['%susermeta' % DB_PREFIX]
        self._message("Checking %s table" % um.name)
        if not self.revert:
            self._check_default_null(um, 'user_id')
            self._check_foreign_key(um, 'user_id', '%s_ibfk1' % um.name, u.name, 'ID', fix_values='delete')
        else:
            self._drop_foreign_key(um, 'user_id', '%s_ibfk1' % um.name, u.name, 'ID', fix_values='delete')
            self._remove_default_null(um, 'user_id')
        print
        
    def _comments_tables(self, db):
        u = db.tables['%susers' % DB_PREFIX]
        p = db.tables['%sposts' % Blog.get_active().db_prefix]
        comments = db.tables['%scomments' % Blog.get_active().db_prefix]
        cm = db.tables['%scommentmeta' % Blog.get_active().db_prefix]
        if not self.revert:
            self._message("Checking %s table" % comments.name)
            self._check_default_null(comments, 'user_id', nullable=True)
            self._check_foreign_key(comments, 'user_id', '%s_ibfk1' % comments.name, u.name, 'ID', 'cascade', 'set null', fix_values='update')
            self._check_default_null(comments, 'comment_parent', nullable=True)
            self._check_foreign_key(comments, 'comment_parent', '%s_ibfk2' % comments.name, comments.name, 'comment_ID', 'cascade', 'set null', fix_values='update')
            self._check_trigger(
                comments, "%s_bi" % comments.name,
                "create trigger %s_bi before insert on %s for each row begin if new.comment_parent = '0' then set new.comment_parent = NULL; end if; if new.user_id = '0' then set new.user_id = NULL; end if; end" % (comments.name, comments.name)
            )
            self._check_default_null(comments, 'comment_post_ID')
            self._check_orphaned_fk(comments, 'comment_post_ID', p, 'ID')
            self._check_foreign_key(comments, 'comment_post_ID', '%s_ibfk3' % comments.name, p.name, 'ID', fix_values='delete')
            print
            self._message("Checking %s table" % cm.name)
            self._check_default_null(cm, 'comment_id')
            self._check_orphaned_fk(cm, 'comment_id', comments, 'comment_ID')
            self._check_foreign_key(cm, 'comment_id', '%s_ibfk1' % cm.name, comments.name, 'comment_ID', fix_values='delete')
        else:
            self._message("Checking %s table" % cm.name)
            self._drop_foreign_key(cm, 'comment_id', '%s_ibfk1' % cm.name, comments.name, 'comment_ID', fix_values='delete')
            self._remove_default_null(cm, 'comment_id')
            print
            self._message("Checking %s table" % comments.name)
            self._drop_foreign_key(comments, 'comment_post_ID', '%s_ibfk3' % comments.name, p.name, 'ID', fix_values='delete')
            self._drop_foreign_key(comments, 'comment_parent', '%s_ibfk2' % comments.name, comments.name, 'comment_ID', 'cascade', 'set null', fix_values='update')
            self._drop_foreign_key(comments, 'user_id', '%s_ibfk1' % comments.name, u.name, 'ID', 'cascade', 'set null', fix_values='update')
            self._drop_trigger(comments, "%s_bi" % comments.name)
            self._remove_default_null(comments, 'comment_post_ID')
            self._remove_default_null(comments, 'comment_parent', nullable=True)
            self._remove_default_null(comments, 'user_id', nullable=True)
        print
        
    def _term_taxonomy_tables(self, db):
        terms = db.tables['%sterms' % Blog.get_active().db_prefix]
        tt = db.tables['%sterm_taxonomy' % Blog.get_active().db_prefix]
        self._message("Checking %s table" % tt.name)
        if not self.revert:
            self._check_default_null(tt, 'term_id')
            fk = tt.field_foreign_keys.get('term_id')
            if not fk:
                print ("%s.%s orphaned" % (tt.name, 'term_id')).ljust(self.justify),
                self._execute(
                    "delete from %s where term_id not in (select term_id from %s)" % (tt.name, terms.name),
                    "%(num)s removed"
                )
            self._check_foreign_key(tt, 'term_id', '%s_ibfk1' % tt.name, terms.name, 'term_id')
            self._check_default_null(tt, 'parent', nullable=True)
            self._check_foreign_key(tt, 'parent', '%s_ibfk2' % tt.name, terms.name, 'term_id', fix_values='update')
            self._check_trigger(
                tt, "%s_bi" % tt.name,
                "create trigger %s_bi before insert on %s for each row begin if new.parent = '0' then set new.parent = NULL; end if; end" % (
                    tt.name, tt.name
                )
            )
        else:
            self._drop_foreign_key(tt, 'parent', '%s_ibfk2' % tt.name, terms.name, 'term_id', fix_values='update')
            self._drop_foreign_key(tt, 'term_id', '%s_ibfk1' % tt.name, terms.name, 'term_id')
            self._drop_trigger(tt, "%s_bi" % tt.name)
            self._remove_default_null(tt, 'parent', nullable=True)
            self._remove_default_null(tt, 'term_id')
        print
        
    def _terms_table(self, db):
        terms = db.tables['%sterms' % Blog.get_active().db_prefix]
        self._message("Checking %s table" % terms.name)
        print ("%s.%s index" % (terms.name, 'term_order')).ljust(self.justify),
        if not self.revert:
            if 'term_order' in terms.fields:
                idx = terms.field_indexes.get('term_order')
                if not idx:
                    self._execute(
                        "alter table %s add index term_order (term_order)" % terms.name,
                        "added"
                    )
            else:
                print "not found, nothing to do"
            print
        else:
            idx = terms.field_indexes.get('term_order')
            if idx:
                print "found, will not remove"
            else:
                print "not found, will not add"
        print
        
    def _posts_tables(self, db):
        p = db.tables['%sposts' % Blog.get_active().db_prefix]
        pm = db.tables['%spostmeta' % Blog.get_active().db_prefix]
        users_name = '%susers' % DB_PREFIX
        
        if not self.revert:
            self._message("Checking %s table" % p.name)
            self._check_default_null(p, 'post_author')
            self._check_default_null(p, 'post_parent', nullable=True)
            self._check_foreign_key(p, 'post_author', '%s_ibfk1' % p.name, users_name, 'ID', fix_values='update')
            self._check_foreign_key(p, 'post_parent', '%s_ibfk2' % p.name, p.name, 'ID', 'set NULL', 'set NULL', fix_values='update')
            self._check_trigger(
                p, "%s_bi" % p.name,
                "create trigger %s_bi before insert on %s for each row begin if new.post_parent = '0' then set new.post_parent = NULL; end if; end" % (
                    p.name, p.name
                )
            )
            self._check_trigger(
                p, "%s_bu" % p.name,
                "create trigger %s_bu before update on %s for each row begin if new.post_parent = '0' then set new.post_parent = NULL; end if; end" % (
                    p.name, p.name
                )
            )
            print
            self._message("Checking %s table" % pm.name)
            self._check_default_null(pm, 'post_id')
            self._check_foreign_key(pm, 'post_id', '%s_ibfk1' % pm.name, p.name, 'ID', fix_values='delete')
            print
            
        else:
            self._message("Checking %s table" % pm.name)
            self._drop_foreign_key(pm, 'post_id', '%s_ibfk1' % pm.name, p.name, 'ID', fix_values='delete')
            self._remove_default_null(pm, 'post_id')
            print
            self._message("Checking %s table" % p.name)
            self._drop_foreign_key(p, 'post_author', '%s_ibfk1' % p.name, users_name, 'ID', fix_values='update')
            self._drop_foreign_key(p, 'post_parent', '%s_ibfk2' % p.name, p.name, 'ID', 'set NULL', 'set NULL', fix_values='update')
            self._drop_trigger(p, "%s_bi" % p.name)
            self._drop_trigger(p, "%s_bu" % p.name)
            self._remove_default_null(p, 'post_author')
            self._remove_default_null(p, 'post_parent', nullable=True)
        print

    def _drop_trigger(self, table, trigger_name):
        print ("%s trigger" % trigger_name).ljust(self.justify),
        trigger = table.triggers.get(trigger_name)
        if trigger is None:
            print "ok (no trigger %s)" % trigger_name
        else:
            self._execute("drop trigger %s" % trigger_name, "dropped")

    def _check_trigger(self, table, trigger_name, q):
        print ("%s trigger" % trigger_name).ljust(self.justify),
        trigger = table.triggers.get(trigger_name)
        if trigger is None:
            self._execute(q, "created")
        else:
            print "already defined (%s %s)" % (trigger['action_timing'].lower(), trigger['event_manipulation'].lower())
            
    def _remove_default_null(self, table, column_name, datatype="bigint unsigned", nullable=False):
        print ("%s.%s default" % (table.name, column_name)).ljust(self.justify),
        field = table.fields[column_name]
        if field['column_default'] is not None or field['is_nullable'] != nullable:
            print "ok (%s)" % table.fields[column_name]['column_default']
        else:
            self._execute(
                "alter table %s change %s %s %s default '0'" % (
                    table.name, column_name, column_name, datatype
                ),
                "restore default value"
            )
            
    def _check_orphaned_fk(self, source_table, source_field, dest_table, dest_field, delete=True):
        if self.revert:
            return
        print ("%s.%s orphaned FKs" % (source_table.name, source_field)).ljust(self.justify),
        if delete:
            self._execute(
                "delete from %s where %s not in (select distinct %s from %s)" % (
                    source_table.name, source_field, dest_field, dest_table.name
                ),
                "removed %(num)s orphaned fk values"
            )
        else:
            self._execute(
                "update %s set %s=NULL where %s not in (select distinct %s from %s)" % (
                    source_table.name, source_field, source_field, dest_field, dest_table.name
                ),
                "changed %(num)s orphaned fk values to NULL"
            )
        
    def _check_default_null(self, table, column_name, datatype="bigint unsigned", nullable=False):
        print ("%s.%s default" % (table.name, column_name)).ljust(self.justify),
        field = table.fields[column_name]
        if field['column_default'] is not None or field['is_nullable'] != nullable:
            self._execute(
                "alter table %s change %s %s %s %s" % (
                    table.name, column_name, column_name, datatype,
                    "not null" if not nullable else "default NULL"
                ),
                "remove default value"
            )
        else:
            print "ok (%s)" % table.fields[column_name]['column_default']
    
    def _drop_foreign_key(self, table, column_name, fk_name, dest_tn, dest_cn, update='cascade', delete='cascade', fix_values=None):
        fk = table.field_foreign_keys.get(column_name)
        if fk and fix_values:
            self._fix_old_defaults(table, column_name, old='NULL', new='0', update=fix_values=='update')
        print ("%s.%s fk" % (table.name, column_name)).ljust(self.justify),
        if fk:
            self._execute(
                "alter table %s drop foreign key %s" % (table.name, fk_name),
                "dropped (%s)" % fk_name
            )
        else:
            print "ok (no foreign key %s)" % fk_name

    def _check_foreign_key(self, table, column_name, fk_name, dest_tn, dest_cn, update='cascade', delete='cascade', fix_values=None):
        fk = table.field_foreign_keys.get(column_name)
        if not fk and fix_values:
            self._fix_old_defaults(table, column_name, update=fix_values=='update')
        print ("%s.%s fk" % (table.name, column_name)).ljust(self.justify),
        if fk:
            print "ok (%s)" % ", ".join(v['constraint_name'] for v in fk)
        else:
            self._execute(
                "alter table %s add constraint %s foreign key (%s) references %s (%s) on update %s on delete %s" % (
                    table.name, fk_name, column_name,
                    dest_tn, dest_cn,
                    update, delete
                ),
                "added (%s)" % fk_name
            )
            
    def _fix_old_defaults(self, table, column_name, old=0, new='NULL', update=True):
        print ("%s.%s default" % (table.name, column_name)).ljust(self.justify),
        if update:
            self._execute(
                "update %s set %s=%s where %s=%s" % (
                    table.name, column_name, new, column_name, old
                ),
                "changed %%(num)s old default values to %s" % new
            )
        else:
            self._execute(
                "delete from %s where %s=%s" % (
                    table.name, column_name, old
                ),
                "removed %(num)s old default values"
            )

    def _innodb(self, db):
        self._message("Checking for InnoDB tables")

        for t in db.tables.values():
            if not t.name.startswith(DB_PREFIX):
                continue
            print t.name.ljust(self.justify),
            
            innodb = (t.engine.lower() == 'innodb')
            if self.revert:
                if innodb:
                    self._execute(
                        "alter table %s engine MyISAM" % t.name,
                        "change from %s to MyISAM" % t.engine
                    )
                else:
                    print 'ok (%s)' % t.engine
            elif innodb:
                print 'ok (%s)' % t.engine
            else:
                self._execute(
                    "alter table %s engine innodb" % t.name,
                    "change from %s to InnoDB" % t.engine
                )
        if not self.dummy:
            db.reset()
        print
        
    def _message(self, m, double=False, line_char='-'):
        if double:
            print
        print m
        print len(m) * line_char
        if double:
            print

    def _execute(self, q, message):
        if self.dummy:
            print "/* start */ %s /* end */" % q
            return
        try:
            res = self.cursor.execute(q)
        except (DatabaseError, OperationalError), e:
            connection._rollback()
            raise CommandError("Cannot execute statement %s error %s" % (q, e))
        if message is not None:
            print message % dict(num=res)
            #print " " * self.justify,
            #print "/* start */ %s /* end */" % q
        return res
    
