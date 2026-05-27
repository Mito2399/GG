from django.apps import AppConfig


# FIX: original code was `class AppConfig(AppConfig):`  — the class name
# shadowed its own base class import, which works in Python but is confusing
# and fragile.  Renamed to AppAppConfig; Django discovers it via default_app_config
# or the 'app' label automatically.
class AppAppConfig(AppConfig):
    name = "app"
    # FIX: set here as well as in settings.py so the app-level default
    # is explicit, suppressing system-check warnings.
    default_auto_field = "django.db.models.BigAutoField"
