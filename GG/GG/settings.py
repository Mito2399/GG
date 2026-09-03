from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security ──────────────────────────────────────────────────────────────────
# Set DJANGO_SECRET_KEY in your environment for production.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-change-me-before-deploying-to-production",
)

# Set DJANGO_DEBUG=False in your environment for production.
# Old
# DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"
# New
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"

# Comma-separated hosts for production, e.g. "example.com,www.example.com"
_allowed = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
# Old
# ALLOWED_HOSTS = _allowed.split(",") if _allowed else (["*"] if DEBUG else [])
# New
ALLOWED_HOSTS = ["*"]

# ── Applications ──────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize", 
    "app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "app.middleware.LoginRateLimitMiddleware",
    "app.middleware.BlockNonAdminMiddleware",
]

ROOT_URLCONF = "GG.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "app.context_processors.role_context",
            ],
        },
    },
]

WSGI_APPLICATION = "GG.wsgi.application"

# ── Database ──────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ── Primary key default type (suppresses system-check warning) ────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Password validation ───────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Internationalisation ──────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE     = "Asia/Manila"
USE_I18N      = True
USE_TZ        = True

# ── Static / media ────────────────────────────────────────────────────────────
STATIC_URL  = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "app/static")]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL   = "/images/"
MEDIA_ROOT  = BASE_DIR / "media"        



# ── App-specific ──────────────────────────────────────────────────────────────
ADMIN_PIN = os.environ.get("ADMIN_PIN", "") 
if not ADMIN_PIN:
    raise RuntimeError(
        "ADMIN_PIN environment variable is not set. "
        "Run: setx ADMIN_PIN \"your-4-digit-pin\""
    )

# ── Backup ────────────────────────────────────────────────────────────────────
BACKUP_OFFLINE_DIR      = os.environ.get("BACKUP_OFFLINE_DIR", str(BASE_DIR / "backups"))
BACKUP_COOLDOWN_MINUTES = 5    
BACKUP_RETENTION_DAYS   = 90    


BACKUP_DAILY_HOUR   = 18  
BACKUP_DAILY_MINUTE = 0


SESSION_COOKIE_AGE     = 28800
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  

