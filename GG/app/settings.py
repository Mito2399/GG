"""
Django settings for GG project.
"""

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
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

# Comma-separated hosts for production, e.g. "example.com,www.example.com"
_allowed = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
ALLOWED_HOSTS = _allowed.split(",") if _allowed else (["*"] if DEBUG else [])

# ── Applications ──────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",   # ← for intcomma / naturaltime in templates
    "app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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
# USE_L10N removed — deprecated since Django 4.0, removed in 5.0+; defaults True.

# ── Static / media ────────────────────────────────────────────────────────────
STATIC_URL  = "static/"
MEDIA_URL   = "/images/"
MEDIA_ROOT  = BASE_DIR / "media"          # ← was missing; needed for any uploads

STATICFILES_DIRS = [os.path.join(BASE_DIR, "app/static")]

# ── App-specific ──────────────────────────────────────────────────────────────
# Set ADMIN_PIN in your environment for production.
ADMIN_PIN = os.environ.get("ADMIN_PIN", "0010")


# ── Automatic Backup ─────────────────────────────────────────────────────────

# Offline — local folder or external drive / USB
BACKUP_OFFLINE_DIR = "D:/Backups/GreenGarden"   # change to your drive path

# Cloud — Dropbox API (free 2 GB, no desktop app needed)
# Get your token at: https://www.dropbox.com/developers/apps
DROPBOX_ACCESS_TOKEN  = "sl.u.AGg_bA6dSM4rjCRj_WSGc2qrymNCaLO1AYsp_vGMLXP2RkPQeiUM_WnC3d7SpsPHqWEKpRUQvHRhasiIB-fTg5FWROODtSts3H6RzBrRe9yUF7H32oBdFRrAAgGXuQ_Y-Lh1XPx6Xfq0MINAOMMARm4F9a5-HCfqaF5pbKu7_xCAngBcPJjdon-hfkie0fagncO6kbipUnmVKnploA7IvJNNmvrvNDEwRiUalf9QYQRX8_3MYHGrT4feq0NuOTKZk25vnvZ55KY2jmzRuwALlLqZQ7so4FUG5yHIISa8LK-9uw2OnkPwq77M-z2mKbwK-X97uHKLnjvfG6YH_IdwhpB7_uMy7NrXQyeRzElYFPSeq9GKx_YC-uRcFYB5iX3rXFmJlM1zq908ZMZDdRI7pWXupsy_cwWLb29Xh3aE4DUCuR4X69Eb_giseq-7xic97dAQ7IL3d21wBKBPYYcuz3DpcwOgOh97kEJdxJDQEJt9jdrcApsu11LWZi9mBfz_2ZpJCyBFrkTCI8gCh0gZFxIsyTBr3XkSRJSOyONO5FX5ZnLsAH8SmBk-BIazPMFSwm01ynuAnSN2zbwvPstMnpDec0f_GlM4lMa1RNuEE8XkgZpmgecKJ3yHA_o2-SiAblJoVwitmM3ugPw4EwUBWgvZOoUhvQKHkEgu-QY9LXCCGjZcDOWteRfcPf1OamQ58XPtE6Ui_O3-tTURjkatBPCCvuRZN3Q8yWEVvrahlkBnS5B46H0AuK3Tp-7UwIdmm0BMQS276akFxmUzEP2AD7jN7wI-mkH30ZwCzw2iiIr4hSTpTch6jSXyFi-XgSWHhU6rzzWch6gliSIINsLRXJkh8XpbODwu90XYiS2AzUGJL7kMZjieWIim6dBPq11N-h3uccooGEZODS63tGRB-mQNlNHjEyRGnbCOzY5NlEQ-Scpz3wKpYujCx87FNL0JxAL5SP6DNsPUmDTV6LYf1nRMLnx1maBMnffFFtpqTY2_OrIPPAIr99XYsibGA8W8uFhTqBnR2MOSwF7iHNXkgTA7EzCVYji8jpq-6l4tUe4jWt9Mg5a4i69k4pdkvPKI5gVoQXF0OAsnvI-1oHpAngmoWfTSkc6PCdjiK1JwcxBU6hwl9n4I3qG6lsM1d3an9h6zpyYtPAgOeX6KQae74kt6dp4rPIBiGcgDXsfRMjrm68DSL_6pKRaGCGuzGSN5MuvojKOpuaXtZeM96KK3P5aBXo_OnlZ3waBR-YW8_uJytDq_hXIuUYb2oRhpOSKdsuSivOwIFBwFueI3HaA9jHksxwsyqslKNt18VXzIDgQu9n8gLYpUHIMaIphhaPcVatkSZK8RUzEZpHKvSq98IhiKILIyZX_FEi-Qqxg9D4f5oFMdu68uObRuc7f3_1A_7iR3bZj40GHkRMYhH6NB-zTW8STh5tKx94xG8IkwLMBEwQ"  # paste your token here
DROPBOX_BACKUP_FOLDER = "/GreenGardenBackups"   # folder that will be created in your Dropbox

# Minimum gap between two backups (prevents flooding during bulk operations)
BACKUP_COOLDOWN_MINUTES = 15

# Backups older than this are auto-deleted from BOTH offline and Dropbox
BACKUP_RETENTION_DAYS = 90
