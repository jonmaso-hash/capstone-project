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
    ANTHROPIC_API_KEY=(str, ''),
    STREAM_API_KEY=(str, ''),
    STREAM_API_SECRET=(str, ''),
    EMAIL_HOST_USER=(str, ''),
    EMAIL_HOST_PASSWORD=(str, ''),
    ADMIN_URL_PATH=(str, 'admin/'),
    CELERY_BROKER_URL=(str, 'redis://localhost:6379/0'),
    CELERY_RESULT_BACKEND=(str, 'redis://localhost:6379/0'),
    # Separate DB index from Celery's /0 above. Empty by default so local
    # dev keeps using LocMemCache without requiring a Redis instance —
    # set this (e.g. via docker-compose) to turn on the Redis-backed cache.
    CACHE_URL=(str, ''),
    AWS_STORAGE_BUCKET_NAME=(str, ''),
    AWS_ACCESS_KEY_ID=(str, ''),
    AWS_SECRET_ACCESS_KEY=(str, ''),
    AWS_S3_REGION_NAME=(str, 'us-east-1'),
    SENTRY_DSN=(str, ''),
    STRIPE_SECRET_KEY=(str, ''),
    STRIPE_PUBLISHABLE_KEY=(str, ''),
    STRIPE_WEBHOOK_SECRET=(str, ''),
    STRIPE_FOUNDER_PRICE_ID=(str, ''),
    STRIPE_INVESTOR_PRICE_ID=(str, ''),
    STRIPE_SELLER_PRICE_ID=(str, ''),
    STRIPE_BUYER_PRICE_ID=(str, ''),
    STRIPE_FIRM_PRICE_ID=(str, ''),
    STRIPE_VALUATION_REPORT_PRICE_ID=(str, ''),
    STRIPE_VALUATION_OVERAGE_PRICE_ID=(str, ''),
    STRIPE_VALUATION_FIRM_OVERAGE_PRICE_ID=(str, ''),
    GOOGLE_OAUTH_CLIENT_ID=(str, ''),
    GOOGLE_OAUTH_SECRET=(str, ''),
    FACEBOOK_OAUTH_CLIENT_ID=(str, ''),
    FACEBOOK_OAUTH_SECRET=(str, ''),
    LINKEDIN_OAUTH_CLIENT_ID=(str, ''),
    LINKEDIN_OAUTH_SECRET=(str, ''),
    # Truth Delta external verification sources. SEC EDGAR needs no key
    # (public data.sec.gov API); these two are optional — Truth Delta
    # degrades to "no corroborating data found" for a source when its key
    # is blank, rather than failing.
    CRUNCHBASE_API_KEY=(str, ''),
    NEWS_API_KEY=(str, ''),
)

# Read parameters straight from your secure root .env file
environ.Env.read_env(BASE_DIR / '.env')




# --- CORE SECURITY CONFIGURATION ---
# Throws an ImproperlyConfigured error if SECRET_KEY is missing in production
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Origins trusted for CSRF-protected POSTs, each with its scheme, e.g.
# "https://interlinkfoundry.com,https://interlink-foundry.onrender.com".
# Needed once the site is served from a domain behind the host's proxy.
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

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
    "django.contrib.sites",
    "django.contrib.sitemaps",
    "jobs.apps.JobsConfig",
    "rest_framework",
    "rest_framework.authtoken",

    # Third-Party Infrastructure Layout Extensions
    "storages",
    "crispy_forms",
    "crispy_bootstrap5",

    # Social Login (Google, Facebook, LinkedIn)
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.facebook",
    "allauth.socialaccount.providers.linkedin_oauth2",

    # Internal Interlink Foundry Apps
    "blog",
    "pages",
    "accounts",
    "matchmaking",
    "zelda_api",
    "usersettings",
    "billing",
    "ops",
    "growth",

    'django_extensions',
    'notifications',
    'sharing',
]

SITE_ID = 1

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
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # Your Unique Idempotency Layer
    'shared_utils.middleware.IdempotencyMiddleware',
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

IDEMPOTENCY_EXCLUDED_PATHS = [
    "/accounts/seeking-investment/",
    "/accounts/logout/",
    "/accounts/login",
    "/api/v1/auth/login/",
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
                'ops.context_processors.active_announcements',
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

CACHE_URL = env('CACHE_URL')
if CACHE_URL:
    # Django's built-in Redis cache backend (4.0+) — no extra dependency,
    # `redis` is already required for the Celery broker/backend above.
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': CACHE_URL,
        }
    }
else:
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
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = env.str('STATIC_ROOT', default=os.path.join(BASE_DIR, 'staticfiles'))

# Static files are served by WhiteNoise from the container in every
# environment -- S3, when configured below, holds uploads only. In production
# they get hashed, compressed filenames, so a browser can never keep a stale
# CSS or JS file after a deploy. That storage raises at render time for any
# {% static %} path missing from the collected manifest, so with DEBUG on
# (local dev, CI) the plain storage is used and no collectstatic is needed.
STATICFILES_BACKEND = (
    "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG
    else "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

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
        "staticfiles": {"BACKEND": STATICFILES_BACKEND},
    }
    MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/media/"
else:
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'

    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {"BACKEND": STATICFILES_BACKEND},
    }

# --- CORE PLATFORM SECURITY & AUTH ROUTING ---
# LOGIN_REDIRECT_URL is set once, in the social-login section below
# (accounts:post_login_router). It used to be assigned here too, as
# accounts:profile_self, which never survived import — the later assignment
# always won — while reading as though password login landed on your own
# profile. It did, but because login_view hardcoded that redirect, not because
# of this setting. Both are fixed in PR #27; the shadowed line is gone.
LOGOUT_REDIRECT_URL = "accounts:login"
LOGIN_URL = "accounts:login"

# Reads from .env in production; falls back to localhost Redis for dev.
CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND')

# Off in prod/dev (tasks go to a real worker). CI/test runs set EAGER True so
# `.delay()` executes in-process — no broker, no worker, and no dependency on
# Celery's redis transport (which has hung `.delay()` calls made from inside a
# live view under this Python/Celery combination). EAGER_PROPAGATES stays off
# by default so an eager task that raises still surfaces as a failed result
# rather than a new exception in the caller.
CELERY_TASK_ALWAYS_EAGER = env.bool('CELERY_TASK_ALWAYS_EAGER', default=False)
CELERY_TASK_EAGER_PROPAGATES = env.bool('CELERY_TASK_EAGER_PROPAGATES', default=False)

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
    'send-priority-match-alerts': {
        'task': 'matchmaking.tasks.send_priority_match_alerts',
        'schedule': crontab(hour=8, minute=0),
    },
    'ensure-next-month-partition': {
        'task': 'matchmaking.tasks.ensure_next_month_partition',
        'schedule': crontab(day_of_month=25, hour=3, minute=0),
    },
    'generate-quarterly-insight-report': {
        'task': 'growth.tasks.generate_quarterly_insight_report',
        'schedule': crontab(day_of_month=1, month_of_year='1,4,7,10', hour=6, minute=0),
    },
}


# --- THIRD-PARTY INTERFACE DESIGN CONFIGURATION ---
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


# --- SOCIAL LOGIN (GOOGLE, FACEBOOK, LINKEDIN) ---
# A brand-new social-login user has no "role" yet (Founder/Investor/Seller/Buyer) —
# post_login_router (accounts:post_login_router) sends them to the role picker
# instead of allauth's own generic signup form, so AUTO_SIGNUP stays on.
SOCIALACCOUNT_AUTO_SIGNUP = True
LOGIN_REDIRECT_URL = 'accounts:post_login_router'

# allauth's default ACCOUNT_SIGNUP_FIELDS includes password1/password2, which
# blocks true one-click social signup: Google/Facebook/LinkedIn never supply a
# password, so AUTO_SIGNUP would otherwise fall back to allauth's own signup
# form asking the brand-new user to set one anyway. Password auth is never
# offered to social-login users — they always sign back in via the provider.
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*"]

# Pulls the provider's profile photo into UserSettings.profile_picture on
# first signup (accounts/adapters.py) — separate from ACCOUNT_ADAPTER, which
# this app doesn't currently override.
SOCIALACCOUNT_ADAPTER = 'accounts.adapters.SocialAccountAdapter'

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': env('GOOGLE_OAUTH_CLIENT_ID'),
            'secret': env('GOOGLE_OAUTH_SECRET'),
            'key': '',
        },
        'SCOPE': ['profile', 'email'],
    },
    'facebook': {
        'APP': {
            'client_id': env('FACEBOOK_OAUTH_CLIENT_ID'),
            'secret': env('FACEBOOK_OAUTH_SECRET'),
            'key': '',
        },
        'FIELDS': ['id', 'first_name', 'last_name', 'name', 'email'],
    },
    'linkedin_oauth2': {
        'APP': {
            'client_id': env('LINKEDIN_OAUTH_CLIENT_ID'),
            'secret': env('LINKEDIN_OAUTH_SECRET'),
            'key': '',
        },
    },
}


# --- INTERLINK FOUNDRY ENVIRONMENT GLOBALS ---
SITE_URL = env('SITE_URL')
ADMIN_EMAIL = env('ADMIN_EMAIL')


# --- THIRD-PARTY API INTEGRATIONS & EMBEDDING ENGINES ---
STREAM_API_KEY = env('STREAM_API_KEY')
STREAM_API_SECRET = env('STREAM_API_SECRET')
ANTHROPIC_API_KEY = env('ANTHROPIC_API_KEY')
# Explicit ceilings for every Anthropic client (zelda_api/anthropic_client.py)
# instead of the SDK's 10-minute timeout with 2 retries. A web-request call's
# worst case, timeout x (retries + 1), must finish inside GUNICORN_TIMEOUT
# (gunicorn.conf.py, default 60s); pages/tests_request_timeouts.py pins that.
ANTHROPIC_WEB_REQUEST_TIMEOUT_SECONDS = env.float('ANTHROPIC_WEB_REQUEST_TIMEOUT_SECONDS', default=25.0)
ANTHROPIC_WEB_REQUEST_MAX_RETRIES = env.int('ANTHROPIC_WEB_REQUEST_MAX_RETRIES', default=0)
ANTHROPIC_BACKGROUND_TIMEOUT_SECONDS = env.float('ANTHROPIC_BACKGROUND_TIMEOUT_SECONDS', default=120.0)
ANTHROPIC_BACKGROUND_MAX_RETRIES = env.int('ANTHROPIC_BACKGROUND_MAX_RETRIES', default=2)
CRUNCHBASE_API_KEY = env('CRUNCHBASE_API_KEY')
NEWS_API_KEY = env('NEWS_API_KEY')

# --- STRIPE PAYMENT PROCESSING ---
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY')
# DEBUG with a live-mode key refuses to start. Local dev must never be able to
# make real Stripe charges. See config/stripe_guard.py.
from config.stripe_guard import refuse_live_stripe_key_in_debug
refuse_live_stripe_key_in_debug(DEBUG, STRIPE_SECRET_KEY)
STRIPE_PUBLISHABLE_KEY = env('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET')
STRIPE_FOUNDER_PRICE_ID = env('STRIPE_FOUNDER_PRICE_ID')
STRIPE_INVESTOR_PRICE_ID = env('STRIPE_INVESTOR_PRICE_ID')
STRIPE_SELLER_PRICE_ID = env('STRIPE_SELLER_PRICE_ID')
STRIPE_BUYER_PRICE_ID = env('STRIPE_BUYER_PRICE_ID')
STRIPE_FIRM_PRICE_ID = env('STRIPE_FIRM_PRICE_ID')
STRIPE_VALUATION_REPORT_PRICE_ID = env('STRIPE_VALUATION_REPORT_PRICE_ID')
STRIPE_VALUATION_OVERAGE_PRICE_ID = env('STRIPE_VALUATION_OVERAGE_PRICE_ID')
STRIPE_VALUATION_FIRM_OVERAGE_PRICE_ID = env('STRIPE_VALUATION_FIRM_OVERAGE_PRICE_ID')


# --- EMAIL ---
# Which backend sends mail follows from what is configured, so the same code
# runs in dev, CI and production:
#   POSTMARK_SERVER_TOKEN set          -> Postmark via django-anymail (production)
#   EMAIL_HOST_USER + _PASSWORD set    -> SMTP (Gmail unless EMAIL_HOST says otherwise)
#   neither                            -> console: mail is printed, never sent
# Django's test runner swaps in its in-memory backend regardless.
POSTMARK_SERVER_TOKEN = env.str('POSTMARK_SERVER_TOKEN', default='')
EMAIL_HOST = env.str('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = False
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')

if POSTMARK_SERVER_TOKEN:
    EMAIL_BACKEND = 'anymail.backends.postmark.EmailBackend'
    ANYMAIL = {'POSTMARK_SERVER_TOKEN': POSTMARK_SERVER_TOKEN}
elif EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# The address mail is sent from. Postmark only delivers from a verified sender
# signature or domain, so production sets DEFAULT_FROM_EMAIL explicitly.
DEFAULT_FROM_EMAIL = env.str('DEFAULT_FROM_EMAIL', default='') or EMAIL_HOST_USER or 'noreply@interlinkfoundry.com'
# The sender of error and mail_admins() mail. Django's default, root@localhost,
# is not a sender Postmark will accept.
SERVER_EMAIL = env.str('SERVER_EMAIL', default='') or DEFAULT_FROM_EMAIL
# Who mail_admins() reaches -- e.g. the Explore moderation alert. Unset, that
# mail silently goes nowhere. Comma-separated addresses; Django 6 deprecates
# (name, address) pairs.
ADMINS = [address.strip() for address in env.list('ADMINS', default=[]) if address.strip()]
# Where the public contact form delivers.
CONTACT_FORM_RECIPIENT = env.str('CONTACT_FORM_RECIPIENT', default='') or ADMIN_EMAIL or DEFAULT_FROM_EMAIL


# ==============================================================================
# LOGGING — console (always) + a rotating file so logs survive restarts.
# Without this, every log line this app already emits via logger.error()/
# logger.warning() throughout matchmaking/zelda_api only ever went to
# console output, which vanishes the moment the process restarts.
# ==============================================================================
# In production the file handler is off: a container's filesystem is discarded
# on every deploy, and several gunicorn workers rotating one file race each
# other. There, logs go to the console (the host collects stdout) and Sentry.
# The file stays a local-dev convenience, on by default only when DEBUG is.
LOG_TO_FILE = env.bool('LOG_TO_FILE', default=DEBUG)
LOG_HANDLERS = ['console', 'file'] if LOG_TO_FILE else ['console']

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
    },
    'root': {
        'handlers': LOG_HANDLERS,
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': LOG_HANDLERS,
            'level': 'INFO',
            'propagate': False,
        },
    },
}

if LOG_TO_FILE:
    LOGS_DIR = BASE_DIR / 'logs'
    os.makedirs(LOGS_DIR, exist_ok=True)
    LOGGING['handlers']['file'] = {
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': LOGS_DIR / 'django.log',
        'maxBytes': 10 * 1024 * 1024,  # 10 MB per file
        'backupCount': 5,
        'formatter': 'verbose',
        'encoding': 'utf-8',
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