import contextlib

from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "speleodb.common"
    verbose_name = "Common"

    def ready(self):
        with contextlib.suppress(ImportError):
            import speleodb.users.signals  # noqa: F401
