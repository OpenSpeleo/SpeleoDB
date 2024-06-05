import contextlib

from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "speleodb.users"
    verbose_name = "Users"

    def ready(self):
        with contextlib.suppress(ImportError):
            import speleodb.users.signals  # noqa: F401
