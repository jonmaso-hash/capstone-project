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
)

# Read parameters straight from your secure root .env file
environ.Env.read_env(BASE_DIR / '.env')




# --- CORE SECURITY CONFIGURATION ---
# Throws an ImproperlyConfigured error if SECRET_KEY is missing in production
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')


# --- APPLICATION DEFINITION ---
INSTALLED_APPS = [
    # Core Django Framework Engines
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "jobs.apps.JobsConfig",
    "rest_framework",
    "rest_framework.authtoken",

    # Third-Party Infrastructure Layout Extensions
    "crispy_forms",
    "crispy_bootstrap5",

    # Internal Interlink Foundry Apps
    "blog",
    "pages",
    "accounts",
    "matchmaking",
    "zelda_api",

    # Platform Vertical Modules
    'real_estate_api',
    'marketing_api',
    'legal_api',
    'banking_api',
    'energy_api',
    'articles_api',
    'automotive_api',
    'hotel_api',
    'insurance_api',
    'jobs_api',
    'logistics_api',
    'marketplace_api',
    'messaging_api',
    
    'django_extensions',
    'notifications',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# FIXED: Removed the duplicate 'shared_utils.middleware.IdempotencyMiddleware' entry
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- STATIC & MEDIA ASSET STORAGE PIPELINES ---
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static", os.path.join(BASE_DIR, 'static'),]
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

import os
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# --- CORE PLATFORM SECURITY & AUTH ROUTING ---
LOGIN_REDIRECT_URL = "accounts:profile_self"
LOGOUT_REDIRECT_URL = "accounts:login"
LOGIN_URL = "accounts:login"

CELERY_BROKER_URL = 'redis://localhost:6379/0'
# COMMENT OUT THE LINE BELOW:
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# UPDATE THESE TWO LINES:
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_STORE_EAGER_RESULT = 'redis://localhost:6379/0'


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