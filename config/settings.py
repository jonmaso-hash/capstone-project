import os
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, True),
    ALLOWED_HOSTS=(list, []),
    SITE_URL=(str, 'http://127.0.0.1:8000'),
    ADMIN_EMAIL=(str, 'jonmaso@gmail.com'),
)

# Load environment variables from .env file
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# --- SECURITY WARNINGS ---
SECRET_KEY = env('SECRET_KEY', default='django-insecure-demo-key')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# --- APPLICATION DEFINITION ---
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "crispy_forms",
    "crispy_bootstrap5",
    "blog",
    "pages",
    "accounts",
    "matchmaking",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- DATABASE CONFIGURATION ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- STATIC & MEDIA STORAGE ---
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --- AUTHENTICATION ROUTING ---
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"
LOGIN_URL = "login"

# --- THIRD-PARTY PACK CRISPY CONFIG ---
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# --- INTERLINK FOUNDRY APPLICATION VARIABLES ---
SITE_URL = env('SITE_URL')
ADMIN_EMAIL = env('ADMIN_EMAIL')

# --- EMAIL TRANSMISSION SETTINGS ---
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='jonmaso@gmail.com')
# Your raw app password should be placed in your local .env file under this exact key name:
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='') 
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER