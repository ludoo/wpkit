from django.core.signals import Signal
from django.db.models.signals import pre_save
from django.utils.html import urlize

from wp_frontman.models import BaseComment


def urlize_comment(sender, instance, **kw):
    if not instance.rawcontent:
        return
    instance.rawcontent = urlize(instance.rawcontent, trim_url_limit=48, nofollow=True)


def register():
    pre_save.connect(urlize_comment, sender=BaseComment, weak=False, dispatch_uid=__name__)
    