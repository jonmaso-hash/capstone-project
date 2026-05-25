from pathlib import Path
import os
import environ

# --- BASE DIRECTORY ROUTING ---
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- ENVIRONMENT VARIABLES ENGINE SETUP ---
# Initialize django-environ structure with type defaults
env = environ.Env(
    DEBUG=(bool, True),
    ALLOWED_HOSTS=(list, []),
    SITE_URL=(str, 'http://127.0.0.1:8000'),
    ADMIN_EMAIL=(str, 'jonmaso@gmail.com'),
    GEMINI_API_KEY=(str, ''),
    STREAM_API_KEY=(str, ''),
    STREAM_API_SECRET=(str, ''),
    EMAIL_HOST_USER=(str, 'jonmaso@gmail.com'),
    EMAIL_HOST_PASSWORD=(str, ''),
)

# Read environment parameters straight from your secure root .env file
# FIXED: Consolidated redundant dual-load declarations down to a single clean routing path
environ.Env.read_env(BASE_DIR / '.env')


# --- CORE SECURITY CONFIGURATION ---
SECRET_KEY = env('SECRET_KEY', default='django-insecure-demo-key')
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

    #Zelda API 
    "zelda_api",

    #Real_estate_ API 
    'real_estate_api',

    #marketing_ API 
    'marketing_api',

    #legal_ API 
    'legal_api',

    #banking_ API 
    'banking_api',

    #energy_ API 
    'energy_api',

    #articles_ API 
    'articles_api',

    #automotive_ API 
    'automotive_api',

    #hotel_ API 
    'hotel_api',

    #insurance_ API 
    'insurance_api',

    #jobs_ API 
    'jobs_api',

    #logistics_ API 
    'logistics_api',

    #marketplace_ API 
    'marketplace_api',

    #messaging_ API 
    'messaging_api',
    
    'django_extensions',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}



MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'shared_utils.middleware.IdempotencyMiddleware',
]
IDEMPOTENCY_EXCLUDED_PATHS = [
    '/api/v1/auth/login/',
    '/api/v1/health/',
    '/admin/',
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
                # Shared context tracking metrics for navigation layout layers
                'matchmaking.context_processors.investor_status',
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
STATICFILES_DIRS = [BASE_DIR / "static"]

# Active media routes to manage PDF Pitch Deck layout allocations
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# --- CORE PLATFORM SECURITY & AUTH ROUTING ---
# Redirect paths configured to cleanly navigate users straight to their interactive workspace hubs
LOGIN_REDIRECT_URL = "accounts:profile_self"
LOGOUT_REDIRECT_URL = "accounts:login"
LOGIN_URL = "accounts:login"

CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# --- THIRD-PARTY INTERFACE DESIGN CONFIGURATION ---
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


# --- INTERLINK FOUNDRY ENVIRONMENT GLOBALS ---
SITE_URL = env('SITE_URL')
ADMIN_EMAIL = env('ADMIN_EMAIL')


# --- THIRD-PARTY API INTEGRATIONS & EMBEDDING ENGINES ---
# Gemini AI Platform Engine (For asynchronous multimodal processing)
GEMINI_API_KEY = env('GEMINI_API_KEY')

# Stream Chat Engine (For real-time secure diligence matchmaking communication)
STREAM_API_KEY = env('STREAM_API_KEY')
STREAM_API_SECRET = env('STREAM_API_SECRET')


# --- EMAIL TRANSMISSION LAYERS (SMTP GMAIL PIPELINES) ---
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD') 
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER