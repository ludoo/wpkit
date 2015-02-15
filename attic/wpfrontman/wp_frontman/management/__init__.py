from django.db.models.signals import post_syncdb

import wp_frontman.models


# connect the signal to add the multiple columns index to the Job table
def add_index_to_jobs(sender, *args, **kw):
    if not wp_frontman.models.Job in kw['created_models']:
        return
    from django.db import connection, DatabaseError
    cursor = connection.cursor()
    db_table = wp_frontman.models.Job._meta.db_table
    try:
        res = cursor.execute("alter table %s add index blog_id_process_timestamp (blog_id, process, tstamp)" % db_table)
    except DatabaseError, e:
        print "Cannot create multiple columns index on %s: %s" % (db_table, e)
    else:
        print "Created multiple columns index on", db_table
    

post_syncdb.connect(add_index_to_jobs, sender=wp_frontman.models, weak=False)
