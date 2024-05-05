import contextlib

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "speleodb.users"
    verbose_name = _("Users")

    def ready(self):
        with contextlib.suppress(ImportError):
            import speleodb.users.signals  # noqa: F401
