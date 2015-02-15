# coding=utf-8

import time
import datetime
import random

from hashlib import md5

from django import forms
from django.db import connection
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import ugettext_lazy as _

from wp_frontman.models import User, UserSignup, BaseComment
from wp_frontman.blog import DB_PREFIX, Blog
from wp_frontman.lib.htmlscanner import clean_fragment
from wp_frontman.lib.spam_filters import apply_filters, FilterHardDeny
from wp_frontman.cache import cache_timestamps
#from utils.htmlstripper import strip_html


class CommentForm(forms.Form):
    
    error_css_class = 'commentform_error'
    
    author = forms.CharField(label=_('Name'), max_length=255)
    author_email = forms.EmailField(label=_('Mail'))
    author_url = forms.URLField(label=_('Website'), required=False)
    remember_info = forms.BooleanField(label=_('Remember me'), required=False, initial=True, help_text=_('Flag this box to rember your personal info between sessions'))
    rawcontent = forms.CharField(_('Comment'), widget=forms.Textarea)
    comment_parent = forms.IntegerField(required=False, initial=None, widget=forms.HiddenInput)
    
    def __init__(self, *args, **kw):
        super(CommentForm, self).__init__(*args, **kw)
        for k, v in self.fields.items():
            if isinstance(v, forms.CharField) and not k in self.initial:
                self.initial[k] = ''

    def save(self, request, post, user=None):
        # we need the post and request, a clean() method would not work
        data = self.cleaned_data.copy()
        remember_info = data.pop('remember_info')
        data.update(dict(
            base_post=post, comment_type='',
            author_ip=request.META.get('REMOTE_ADDR'),
            agent=request.META.get('HTTP_USER_AGENT'),
        ))
        # check if we have a user (we should never have one in this form but check anyway)
        if not user:
            user = User.user_from_cookie(request)
        if user:
            data['user'] = user
        # check if we have a parent comment
        data['parent'] = data['comment_parent']
        del data['comment_parent']
        if data.get('parent'):
            try:
                data['parent'] = BaseComment.objects.get(id=data['parent'])
            except ObjectDoesNotExist:
                data['parent'] = None
        comment = BaseComment(**data)
        try:
            comment.approved = apply_filters(comment, request=request)
        except FilterHardDeny, e:
            errorlist = self._errors.setdefault('__all__', self.error_class())
            errorlist.append(e.args[0])
            raise ValueError(e.args[0])
        # TODO: trap exceptions raised by save
        comment.save()
        cache_timestamps(
            Blog.get_active().blog_id,
            'comment',
            dict(id=comment.id, post_id=comment.base_post_id),
            time.time()
        )
        return comment

    
class UserCommentForm(forms.Form):
    
    error_css_class = 'commentform_error'
    
    rawcontent = forms.CharField(_('Comment'), widget=forms.Textarea)
    comment_parent = forms.IntegerField(required=False, initial=None, widget=forms.HiddenInput)
    
    def save(self, request, post, user):
        data = self.cleaned_data.copy()
        data.update(dict(
            base_post=post, comment_type='',
            user=user, author=user.nicename, author_email=user.email,
            author_url=user.url or '',
            author_ip=request.META.get('REMOTE_ADDR'),
            agent=request.META.get('HTTP_USER_AGENT'),
        ))
        # check if we have a parent comment
        data['parent'] = data['comment_parent']
        del data['comment_parent']
        if data.get('parent'):
            try:
                data['parent'] = BaseComment.objects.get(id=data['parent'])
            except ObjectDoesNotExist:
                data['parent'] = None
        comment = BaseComment(**data)
        try:
            comment.approved = apply_filters(comment, request=request)
        except FilterHardDeny, e:
            errorlist = self._errors.setdefault('__all__', self.error_class())
            errorlist.append(e.args[0])
            raise ValueError(e.args[0])
        # TODO: trap exceptions raised by save
        comment.save()
        cache_timestamps(
            Blog.get_active().blog_id,
            'comment',
            dict(id=comment.id, post_id=comment.base_post_id),
            time.time()
        )
        return comment


class LoginForm(forms.Form):
    
    user_login = forms.CharField(label=_('Username'), max_length=16)
    user_pass = forms.CharField(label=_('Password'), widget=forms.PasswordInput)
    rememberme = forms.BooleanField(label=_('Remember Me'), required=False, initial=True)
    
    def __init__(self, *args, **kw):
        kw['auto_id'] ='%s'
        super(LoginForm, self).__init__(*args, **kw)
    
    def clean(self):
        data = super(LoginForm, self).clean()
        login, passwd = data.get('user_login'), data.get('user_pass')
        if not login:
            raise forms.ValidationError(_("The username field is empty"))
        if not passwd:
            raise forms.ValidationError(_("The password field is empty"))
        user = User.user_from_login(login, passwd)
        if not user:
            raise forms.ValidationError(_("Invalid login or password"))
        data['user'] = user
        return data
    
    @property
    def form_errors(self):
        return self.errors.get('__all__')
    
class RegistrationForm(forms.Form):
    
    login = forms.CharField(label=_('Username'), help_text=_("(Must be at least 4 characters, letters and numbers only.)"), max_length=16)
    email = forms.EmailField(label=_('Email Address'), help_text=_("We send your registration email to this address. (Double-check your email address before continuing.)"))
    
    def clean_login(self):
        login = self.cleaned_data['login']
        for c in login:
            if not c in 'abcdefghijklmnopqrstuxvwxyz0123456789':
                raise forms.ValidationError(_("Only lowercase letters (a-z) and numbers are allowed."))
        cursor = connection.cursor()
        if cursor.execute("select ID from %susers where user_login=%%s" % DB_PREFIX, (login,)):
            raise forms.ValidationError(_("Sorry, that username already exists!"))
        if cursor.execute("select user_login from %ssignups where user_login=%%s" % DB_PREFIX, (login,)):
            raise forms.ValidationError(_("That username is currently reserved but may be available in a couple of days."))
        return login
            
    def clean_email(self):
        email = self.cleaned_data['email']
        cursor = connection.cursor()
        if cursor.execute("select ID from %susers where user_email=%%s" % DB_PREFIX, (email,)):
            raise forms.ValidationError("Sorry, that email address is already used!")
        if cursor.execute("select user_login from %ssignups where user_email=%%s" % DB_PREFIX, (email,)):
            raise forms.ValidationError(_("That email address has already been used. Please check your inbox for an activation email. It will become available in a couple of days if you do nothing."))
        return email
    
    def save(self):
        # we need the post and request, a clean() method would not work
        data = self.cleaned_data.copy()
        data['activation_key'] = md5("%s%s%s" % (time.time(), random.random(), data['email'])).hexdigest()[:16]
        s = UserSignup(**data)
        s.save()
            