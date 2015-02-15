from urlparse import urljoin

from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.signals import Signal
from django.core.mail import EmailMultiAlternatives
from django.db.models.signals import post_save
from django.template import loader, Context, TemplateDoesNotExist

from wp_frontman.models import UserSignup
from wp_frontman.blog import Blog


def notify_user(sender, instance, **kw):
    
    blog = Blog.get_active()
    context = Context(dict(
        blog=blog, signup=instance,
        activation_url=urljoin(blog.site.siteurl, reverse('wpf_user_activation'))
    ))
    subject = '[{{blog.blogname}}] New user registration'
    subject = loader.get_template_from_string(subject).render(context)

    try:
        text = loader.get_template('wp_frontman/%s_signup_notification.txt' % blog.blog_id).render(context)
    except TemplateDoesNotExist:
        text = loader.get_template('wp_frontman/signup_notification.txt').render(context)
    
    msg = EmailMultiAlternatives(subject, text, blog.site.admin_email, [instance.email])

    try:
        html = loader.get_template('wp_frontman/%s_signup_notification.html' % blog.blog_id).render(context)
    except TemplateDoesNotExist:
        try:
            html = loader.get_template('wp_frontman/signup_notification.html').render(context)
        except TemplateDoesNotExist:
            html = None
    if html:
        msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=True)


def register():
    post_save.connect(notify_user, sender=UserSignup, weak=False, dispatch_uid=__name__)
    