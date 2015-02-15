from django.conf import settings
from django.core.signals import Signal
from django.core.mail import EmailMultiAlternatives
from django.db.models.signals import post_save
from django.template import loader, Context, TemplateDoesNotExist

from wp_frontman.models import User, BaseComment
from wp_frontman.blog import Blog


NOTIFY_AUTHOR_ONLY = getattr(settings, 'WPF_COMMENT_NOTIFY_AUTHOR_ONLY', True)


def notify_comment(sender, instance, **kw):
    
    if instance.approved == 'spam':
        return
    
    recipients = list()
    
    blog = Blog.get_active()
    
    if (instance.approved in (0, '0') and blog.moderation_notify) or not NOTIFY_AUTHOR_ONLY:
        recipients = [u.email for u in User.objects.can('moderate_comments')]
    else:
        recipients = list()
        
    if blog.comments_notify and instance.approved in (1, '1'):
        user = instance.base_post.author
        if not user.email in recipients:
            if not instance.user_id or instance.user.id != user.id:
                recipients.append(user.email)

    if not recipients:
        return
    
    context = Context(dict(blog=blog, comment=instance))
    
    if instance.approved in (0, '0'):
        subject = '[{{blog.blogname}}] A new {% if comment.comment_type %}{{comment.comment_type}}{% else %}comment{% endif %} on the post "{{comment.base_post.title|striptags}}" is waiting for your approval'
    else:
        subject = '[{{blog.blogname}}] New {% if comment.comment_type %}{{comment.comment_type}}{% else %}comment{% endif %} on post "{{comment.base_post.title|striptags}}"'
    
    if instance.comment_type == '':
        email = instance.author_email
    else:
        email = blog.admin_email

    subject = loader.get_template_from_string(subject).render(context)

    text = html = ''
    
    if instance.comment_type:
        try:
            text = loader.get_template('wp_frontman/%s_notification.txt' % instance.comment_type).render(context)
        except TemplateDoesNotExist:
            pass
        try:
            html = loader.get_template('wp_frontman/comment_notification.html').render(context)
        except TemplateDoesNotExist:
            pass
    if not text:
        text = loader.get_template('wp_frontman/comment_notification.txt').render(context)
    
    msg = EmailMultiAlternatives(subject, text, email, recipients)

    if not html:
        try:
            html = loader.get_template('wp_frontman/comment_notification.html').render(context)
        except TemplateDoesNotExist:
            pass
        else:
            msg.attach_alternative(html, "text/html")
    
    msg.send(fail_silently=True)


def register():
    post_save.connect(notify_comment, sender=BaseComment, weak=False, dispatch_uid=__name__)
    