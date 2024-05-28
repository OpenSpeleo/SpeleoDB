import contextlib

from django.apps import AppConfig


class SurveysConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "speleodb.surveys"
    verbose_name = "Surveys"

    def ready(self):
        with contextlib.suppress(ImportError):
            import speleodb.users.signals  # noqa: F401
