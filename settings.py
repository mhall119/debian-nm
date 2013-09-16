# Django settings for nm project.

from django.conf import global_settings
import os.path
import datetime

PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(PROJECT_DIR, 'data')

DEBUG = False
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ('Debian New Member Frontdesk', 'nm@debian.org'),
)
MANAGERS = ADMINS

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'UTC'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = ''

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_dacs.auth.DACSRemoteUserMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'backend.auth.NMInfoMiddleware',
)

AUTHENTICATION_BACKENDS = (
    # Uncomment to authenticate via REMOTE_USER supplied either by Apache or by
    # DACS_TEST_USERNAME, and using backend.Person as the authoritative user
    # database
    'backend.auth.NMUserBackend',
)

AUTH_PROFILE_MODULE = 'backend.Person'

ROOT_URLCONF = 'urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    "./", "templates"
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Uncomment the next line to enable the admin:
    'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    'django.contrib.admindocs',
    'django.contrib.markup',
    'django_dacs',
    'keyring',
    'dsa',
    'deblayout',
    'nmlayout',
    'backend',
    'public',
    'restricted',
    'maintenance',
    'projectb',
    'minechangelogs',
    'api',
    'south',
)

TEMPLATE_CONTEXT_PROCESSORS = global_settings.TEMPLATE_CONTEXT_PROCESSORS + (
    "django.core.context_processors.request",
    "backend.context_processors.const",
    "backend.context_processors.current_user",
)

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}

# BACKUP_DIR = "/srv/nm.debian.org/backup"
BACKUP_DIR="."
#KEYRINGS = "/home/enrico/dev/deb/keyring.debian.org/keyrings"
KEYRINGS = os.path.join(DATA_DIR, "keyrings")
LDAP_SERVER = "ldap://db.debian.org"
MINECHANGELOGS_CACHEDIR = os.path.join(DATA_DIR, "mc_cache")
MINECHANGELOGS_INDEXDIR = os.path.join(DATA_DIR, "mc_index")

EMAIL_PUBLIC_ANNOUNCES = "enrico@enricozini.org"
EMAIL_PRIVATE_ANNOUNCES = "enrico@enricozini.org"
EMAIL_PERSONAL_DIVERT = ["enrico@enricozini.org"]
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = '/tmp/nm_notification_mails'

PROCESS_MAILBOX_DIR = os.path.abspath("./test-mboxes")

DM_IMPORT_DATE = datetime.datetime(2012, 3, 14)

# The password for this account is available from: master.debian.org:/home/debian/misc/rt-password
RT_LOGIN_INFO = {'user': "debian", 'pass': "the_guest_password"}

# Try importing local settings from local_settings.py, if we can't, it's just fine, use defaults from this file
try:
    from local_settings import *
except:
    pass
