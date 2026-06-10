from django.apps import AppConfig


class AppAppConfig(AppConfig):
    name = "app"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Register backup signals when Django starts.
        import app.signals  # noqa: F401
