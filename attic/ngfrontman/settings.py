import os
import sys
import platform


node = platform.node()

WP_ROOT = '/var/virtual/wp/wordpress' # only for serving themes media files
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
BASE_URL = 'http://ludolo.it'

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ('ludo', 'ludo@qix.it'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'wpf',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}

TIME_ZONE = 'Europe/Rome'
LANGUAGE_CODE = 'en-us'
SITE_ID = 1
USE_I18N = True
USE_L10N = True

MEDIA_URL = '%s/site_media/' % BASE_URL
MEDIA_ROOT = '%s/media/' % BASE_PATH
#ADMIN_MEDIA_PREFIX = "%sadmin/" % MEDIA_URL
STATIC_URL = '%s/static/' % BASE_URL

SECRET_KEY = ''

TEMPLATE_LOADERS = (
    'wp_frontman.template.loaders.filesystem.Loader',
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.core.context_processors.debug",
    "django.core.context_processors.media",
    "django.core.context_processors.request",
    'wp_frontman.context_processors.wpf_blog',
)

MIDDLEWARE_CLASSES = (
    'wp_frontman.middleware.BlogMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

ROOT_URLCONF = 'ngfrontman.urls'

TEMPLATE_DIRS = ('templates',)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'wp_frontman',
)

FORCE_SCRIPT_NAME = ''
CACHE_MIDDLEWARE_SECONDS = 1800

if DEBUG:
    DATABASES['test'] = DATABASES['default']
    DATABASES['test_multi'] = DATABASES['default'].copy()
    DATABASES['test_multi']['NAME'] = 'wpf_multi'
    TEST_RUNNER = 'wp_frontman.lib.test_runner.TestRunner'
