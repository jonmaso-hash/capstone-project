from pathlib import Path
import os
import environ
from dotenv import load_dotenv
load_dotenv()


# --- BASE DIRECTORY ROUTING ---
BASE_DIR = Path(__file__).resolve().parent.parent

# --- ENVIRONMENT VARIABLES ENGINE SETUP ---
# Initialize django-environ structure with strict, non-leaking defaults
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    SITE_URL=(str, 'https://interlinkfoundry.com'),
    ADMIN_EMAIL=(str, ''),
    SECRET_KEY=(str, None),
    GEMINI_API_KEY=(str, ''),
    ANTHROPIC_API_KEY=(str, ''),   
    STREAM_API_KEY=(str, ''),
    STREAM_API_SECRET=(str, ''),
    EMAIL_HOST_USER=(str, ''),
    EMAIL_HOST_PASSWORD=(str, ''),
    ADMIN_URL_PATH=(str, 'admin/'),
    CELERY_BROKER_URL=(str, 'redis://localhost:6379/0'),
    CELERY_RESULT_BACKEND=(str, 'redis://localhost:6379/0'),
    AWS_STORAGE_BUCKET_NAME=(str, ''),
    AWS_ACCESS_KEY_ID=(str, ''),
    AWS_SECRET_ACCESS_KEY=(str, ''),
    AWS_S3_REGION_NAME=(str, 'us-east-1'),
    SENTRY_DSN=(str, ''),
)

# Read parameters straight from your secure root .env file
environ.Env.read_env(BASE_DIR / '.env')




# --- CORE SECURITY CONFIGURATION ---
# Throws an ImproperlyConfigured error if SECRET_KEY is missing in production
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Non-default admin path — defaults to 'admin/' for local dev convenience,
# but production should set ADMIN_URL_PATH in .env to something unguessable.
ADMIN_URL_PATH = env('ADMIN_URL_PATH')
if not ADMIN_URL_PATH.endswith('/'):
    ADMIN_URL_PATH += '/'


# --- APPLICATION DEFINITION ---
INSTALLED_APPS = [
    # Core Django Framework Engines
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "jobs.apps.JobsConfig",
    "rest_framework",
    "rest_framework.authtoken",

    # Third-Party Infrastructure Layout Extensions
    "storages",
    "crispy_forms",
    "crispy_bootstrap5",

    # Internal Interlink Foundry Apps
    "blog",
    "pages",
    "accounts",
    "matchmaking",
    "zelda_api",
    "usersettings",

    'django_extensions',
    'notifications',
]

from django.contrib.messages import constants as message_constants
MESSAGE_TAGS = {
    message_constants.ERROR: 'danger',
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'enterprise_api': '100/hour',
    },
}

# FIXED: Removed the duplicate 'shared_utils.middleware.IdempotencyMiddleware' entry
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    
    # Your Unique Idempotency Layer
    'shared_utils.middleware.IdempotencyMiddleware',
]

IDEMPOTENCY_EXCLUDED_PATHS = [
    "/accounts/seeking-investment/",
    "/accounts/logout/",
    "/accounts/login",
    "/api/v1/auth/login/",
    "/api/v1/health/",
    "/admin/",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                'matchmaking.context_processors.investor_status',
                'notifications.context_processors.notifications',
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- DATABASE LAYER ---
# Reads DATABASE_URL from .env when present (e.g. postgres://user:pass@host:5432/dbname)
# for production; falls back to local SQLite so dev setups need no config at all.
import dj_database_url

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 10},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- STATIC & MEDIA ASSET STORAGE PIPELINES ---
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static", os.path.join(BASE_DIR, 'static'),]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME')

# Local filesystem storage is fine for dev, but doesn't survive container
# restarts or work across multiple app instances in production. When
# AWS_STORAGE_BUCKET_NAME is set in .env, uploads (pitch decks, pitch
# videos, CIMs, Zelda documents) go to S3 instead — nothing else in the
# app needs to change since all uploads already go through Django's
# default_storage / FileField API.
if AWS_STORAGE_BUCKET_NAME:
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {"location": "media"},
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {"location": "static"},
        },
    }
    MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/media/"
else:
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'

    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

# --- CORE PLATFORM SECURITY & AUTH ROUTING ---
LOGIN_REDIRECT_URL = "accounts:profile_self"
LOGOUT_REDIRECT_URL = "accounts:login"
LOGIN_URL = "accounts:login"

# Reads from .env in production; falls back to localhost Redis for dev.
CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND')

CELERY_TASK_ALWAYS_EAGER = False

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'send-weekly-digests': {
        'task': 'matchmaking.tasks.send_weekly_digests',
        'schedule': crontab(day_of_week='monday', hour=9, minute=0),
    },
    'snapshot-investor-predictions': {
        'task': 'matchmaking.tasks.snapshot_investor_predictions',
        'schedule': crontab(day_of_week='wednesday', hour=9, minute=0),
    },
    'snapshot-buyer-predictions': {
        'task': 'matchmaking.tasks.snapshot_buyer_predictions',
        'schedule': crontab(day_of_week='thursday', hour=9, minute=0),
    },
}


# --- THIRD-PARTY INTERFACE DESIGN CONFIGURATION ---
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


# --- INTERLINK FOUNDRY ENVIRONMENT GLOBALS ---
SITE_URL = env('SITE_URL')
ADMIN_EMAIL = env('ADMIN_EMAIL')


# --- THIRD-PARTY API INTEGRATIONS & EMBEDDING ENGINES ---
GEMINI_API_KEY = env('GEMINI_API_KEY')
STREAM_API_KEY = env('STREAM_API_KEY')
STREAM_API_SECRET = env('STREAM_API_SECRET')
ANTHROPIC_API_KEY = env('ANTHROPIC_API_KEY') 


# --- EMAIL TRANSMISSION LAYERS (SMTP GMAIL PIPELINES) ---
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD') 
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


# ==============================================================================
# LOGGING — console (always) + a rotating file so logs survive restarts.
# Without this, every log line this app already emits via logger.error()/
# logger.warning() throughout matchmaking/zelda_api only ever went to
# console output, which vanishes the moment the process restarts.
# ==============================================================================
LOGS_DIR = BASE_DIR / 'logs'
os.makedirs(LOGS_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'django.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB per file
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}


# --- ERROR TRACKING (Sentry) ---
# No-op until SENTRY_DSN is set in .env — sign up at sentry.io, create a
# project, and paste its DSN in to actually start receiving error reports.
SENTRY_DSN = env('SENTRY_DSN')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            # Mirrors the LOGGING config above — anything logged at ERROR
            # or above also gets reported to Sentry as an event.
            LoggingIntegration(level=None, event_level='ERROR'),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )


# ==============================================================================
# PRODUCTION ENVIRONMENT ISOLATION & ENHANCED SECURITY WORKSPACE
# ==============================================================================
if not DEBUG:
    # Route traffic through secure proxy SSL handling mechanisms (Nginx/ALB)
    SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # HTTP Strict Transport Security (HSTS) configuration layers
    SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Cookie security defenses against XSS/Session Hijacking
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # Client-side validation header safeguards
    SECURE_CONTENT_TYPE_NOSNIFF = True