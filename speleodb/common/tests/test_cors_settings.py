from urllib.parse import urlsplit

from django.conf import settings


def test_production_cors_origins_do_not_include_object_store_paths() -> None:
    for origin in settings.PRODUCTION_CORS_ALLOWED_ORIGINS:
        assert urlsplit(origin).path in ("", "/"), origin
