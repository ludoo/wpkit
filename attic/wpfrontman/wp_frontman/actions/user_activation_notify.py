from urlparse import urljoin

from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.signals import Signal
from django.core.mail import EmailMultiAlternatives
from django.db.models.signals import post_save
from django.template import loader, Context, TemplateDoesNotExist

from wp_frontman.models import User
from wp_frontman.blog import Blog


def notify_password(sender, instance, created=False, **kw):
    
    if not created:
        return
    
    blog = Blog.get_active()
    context = Context(dict(
        blog=blog, user=instance,
        profile_url=urljoin(blog.site.siteurl, reverse('wpf_user_profile'))
    ))
    subject = '[{{blog.blogname}}] New user activated'
    subject = loader.get_template_from_string(subject).render(context)

    try:
        text = loader.get_template('wp_frontman/%s_activation_notification.txt' % blog.blog_id).render(context)
    except TemplateDoesNotExist:
        text = loader.get_template('wp_frontman/activation_notification.txt').render(context)
    
    msg = EmailMultiAlternatives(subject, text, blog.site.admin_email, [instance.email])

    try:
        html = loader.get_template('wp_frontman/%s_activation_notification.html' % blog.blog_id).render(context)
    except TemplateDoesNotExist:
        try:
            html = loader.get_template('wp_frontman/activation_notification.html').render(context)
        except TemplateDoesNotExist:
            html = None
    if html:
        msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=True)


def register():
    post_save.connect(notify_password, sender=User, weak=False, dispatch_uid=__name__)
    