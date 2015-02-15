from django.core.signals import Signal
from django.db.models.signals import pre_save

from wp_frontman.models import BaseComment
from wp_frontman.lib.htmlscanner import clean_fragment


def sanitize_html(sender, instance, **kw):
    if not instance.rawcontent:
        return
    instance.rawcontent = clean_fragment(instance.rawcontent)
    # TODO: maybe also add a pass with django.utils.html.clean_html
    

def register():
    pre_save.connect(sanitize_html, sender=BaseComment, weak=False, dispatch_uid=__name__)
    