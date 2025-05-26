import contextlib

from django.apps import AppConfig


class SurveysConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "speleodb.surveys"
    verbose_name = "Surveys"

    def ready(self) -> None:
        with contextlib.suppress(ImportError):
            import speleodb.users.signals  # type: ignore # noqa: F401, PGH003
