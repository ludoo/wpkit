import os
import sys
import platform


node = platform.node()


BASE_PATH = os.path.dirname(os.path.abspath(__file__))
BASE_URL = 'http://127.0.0.1:8081'

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'wpf',
        'USER': '',
        'PASSWORD': '',
        'HOST': '/var/run/mysqld/mysqld.sock',
        'PORT': '',
    }
}

if node == 'SPD-MAGNOCAVALLO':
    DATABASES['default']['HOST'] = '192.168.56.101'

TIME_ZONE = 'Europe/Rome'
LANGUAGE_CODE = 'en-us'
SITE_ID = 1
USE_I18N = True
USE_L10N = True

MEDIA_URL = '%s/site_media/' % BASE_URL
MEDIA_ROOT = '%s/media/' % BASE_PATH
ADMIN_MEDIA_PREFIX = "%sadmin/" % MEDIA_URL

SECRET_KEY = ''

TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.core.context_processors.debug",
    "django.core.context_processors.media",
    "django.core.context_processors.request",
)

MIDDLEWARE_CLASSES = (
    'wp_frontman.middleware.WPFrontmanPageFallbackMiddleware',
    'wp_frontman.middleware.WPFBlogMiddleware',
    'django.middleware.common.CommonMiddleware',
#    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
#    'django.contrib.auth.middleware.AuthenticationMiddleware',
#    'django.contrib.messages.middleware.MessageMiddleware',
)

ROOT_URLCONF = 'wpf.urls'

TEMPLATE_DIRS = (
    '%s/themes/twentyten' % BASE_PATH,
)

INSTALLED_APPS = (
#    'django.contrib.auth',
#    'django.contrib.contenttypes',
#    'django.contrib.sessions',
#    'django.contrib.sites',
#    'django.contrib.messages',
    'wp_frontman',
)

FORCE_SCRIPT_NAME = ''

WPF_WP_LOGGED_IN_KEY = 'y*,5Ba}570tONyq-W3|8iv%JP]GVQ?IF.JJ,Trkj>n.do=ySLG=UcFDl--0;.M@e'
WPF_WP_LOGGED_IN_SALT = 't;do+P%$c-GLxJ]9M!Mk|JEE+xGhRpJ5,6_GAWHUQMQL2A6C/hEj3/;<?@A]BPAN'

DATABASES['test'] = DATABASES['default']
TEST_RUNNER = 'wp_frontman.lib.test_runner.TestRunner'
