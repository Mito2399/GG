import os
import sys
import socket
import threading
import webbrowser

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GG.settings")

# Make sure Python can find the project when run as a frozen .exe
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

import django
django.setup()

from django.conf import settings as dj_settings
from django.core.management import call_command
from django.contrib.auth.models import User

from waitress import serve
from GG.wsgi import application


# ── Default admin credentials (change these before building) ──────────────
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "changeme123"   # ⚠ change this, or change it after first login
DEFAULT_ADMIN_EMAIL    = ""


def _detect_cache_table_name():
    """
    Return the LOCATION (physical table name) of the default cache backend
    IF AND ONLY IF it is Django's database-backed cache. Otherwise None.
    """
    try:
        cfg     = dj_settings.CACHES.get("default", {})
        backend = cfg.get("BACKEND", "")
        if "django.core.cache.backends.db" in backend:
            return cfg.get("LOCATION") or "gg_cache_table"
    except Exception:
        pass
    return None


def ensure_database_ready():
    """
    Runs on every startup. Safe to run repeatedly — idempotent.

      1. Applies pending migrations (creates db.sqlite3 + all app tables).
      2. Creates the Django cache table if the cache backend is DatabaseCache.
      3. Creates a default superuser ONLY if no superuser exists yet.
    """
    print("Checking database...")

    # ── 1. Migrations ─────────────────────────────────────────────────────
    # `migrate` accepts interactive=False — pass it so nothing prompts.
    try:
        call_command("migrate", interactive=False, verbosity=1)
    except Exception as exc:
        print(f"ERROR: Migration failed — {exc}")
        raise

    # ── 2. Cache table ────────────────────────────────────────────────────
    # `createcachetable` does NOT accept interactive. It only accepts:
    #   [tablename] [--database] [--dry-run] [--verbosity]
    # Passing `interactive=False` here raises:
    #   TypeError: Unknown option(s) for createcachetable command: interactive.
    cache_table = _detect_cache_table_name()
    if cache_table:
        try:
            call_command("createcachetable", cache_table, verbosity=0)
            print(f"Cache table ready — '{cache_table}'")
        except Exception as exc:
            print(f"ERROR: Could not create cache table '{cache_table}' — {exc}")
            raise

    # ── 3. Default superuser ──────────────────────────────────────────────
    if not User.objects.filter(is_superuser=True).exists():
        print(f"No admin account found — creating default admin '{DEFAULT_ADMIN_USERNAME}'...")
        User.objects.create_superuser(
            username=DEFAULT_ADMIN_USERNAME,
            email=DEFAULT_ADMIN_EMAIL,
            password=DEFAULT_ADMIN_PASSWORD,
        )
        print(f"Default admin created — username: '{DEFAULT_ADMIN_USERNAME}', password: '{DEFAULT_ADMIN_PASSWORD}'")
        print("IMPORTANT: Log in and change this password immediately.")
    else:
        print("Admin account already exists — skipping creation.")


def get_lan_ip():
    """Find this computer's LAN address automatically."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    ensure_database_ready()

    ip  = get_lan_ip()
    url = f"http://{ip}:8000"

    print("=" * 55)
    print(" GREEN GARDEN SERVER IS RUNNING")
    print("=" * 55)
    print(f" Other computers connect using: {url}")
    print(" Keep this window open while staff are using GG.")
    print(" Close this window to stop the system.")
    print("=" * 55)

    # Auto-open the homepage on THIS computer too
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    try:
        serve(application, host="0.0.0.0", port=8000, threads=8)
    except KeyboardInterrupt:
        print("\nServer stopped.")
