from __future__ import annotations

from http import HTTPStatus
from importlib import reload

import pytest
from django.http import Http404
from django.template import Context
from django.template import Template
from django.test import RequestFactory
from django.test import override_settings
from django.urls import NoReverseMatch
from django.urls import clear_url_caches
from django.urls import path
from django.urls import reverse

from config import urls as application_urls
from speleodb.common.development import vite_generation
from speleodb.common.management.commands.dump_url_config import collect_and_filter_urls
from speleodb.common.templatetags import vite_assets

urlpatterns = [
    path("__assets__/generation/", vite_generation, name="vite-development-generation")
]


def test_generation_endpoint_is_debug_only_and_not_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vite_assets,
        "_manifest",
        lambda: {
            "app.ts": {"file": "assets/dev/session-a/2/app.js", "isEntry": True},
        },
    )
    monkeypatch.setattr(
        vite_assets,
        "_entry_registry",
        lambda: {"scripts": {"app": "app.ts"}, "styles": {}},
    )
    request = RequestFactory().get("/__assets__/generation/")
    with override_settings(DEBUG=True):
        response = vite_generation(request)
        assert response.content == b'{"generation": "session-a/2"}'
        assert "no-store" in response["Cache-Control"]
        assert (
            vite_generation(RequestFactory().post(request.path)).status_code
            == HTTPStatus.METHOD_NOT_ALLOWED
        )
    with override_settings(DEBUG=False), pytest.raises(Http404):
        vite_generation(request)


def test_app_generation_and_url_are_from_its_render_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vite_assets,
        "_manifest",
        lambda: {
            "app.ts": {"file": "assets/dev/session-a/2/app.js", "isEntry": True},
        },
    )
    monkeypatch.setattr(
        vite_assets,
        "_entry_registry",
        lambda: {"scripts": {"app": "app.ts"}, "styles": {}},
    )
    template = Template("{% load vite_assets %}{% vite_script 'app' %}")
    with override_settings(
        DEBUG=True, ROOT_URLCONF=__name__, VITE_ALLOW_MISSING_MANIFEST=True
    ):
        html = template.render(Context())
        assert 'data-speleodb-generation="session-a/2"' in html
        assert 'data-speleodb-reload="/__assets__/generation/"' in html
    with override_settings(DEBUG=False, VITE_ALLOW_MISSING_MANIFEST=True):
        html = template.render(Context())
        assert "data-speleodb-generation" not in html
        assert "data-speleodb-reload" not in html


def test_reload_route_is_debug_only_and_outside_the_public_url_contract() -> None:
    try:
        with override_settings(DEBUG=True, ROOT_URLCONF="config.urls"):
            reload(application_urls)
            clear_url_caches()
            assert reverse("vite-development-generation") == "/__assets__/generation/"
            assert not any(
                route["url"].startswith("/__assets__/")
                for route in collect_and_filter_urls()
            )
        with override_settings(DEBUG=False, ROOT_URLCONF="config.urls"):
            reload(application_urls)
            clear_url_caches()
            with pytest.raises(NoReverseMatch):
                reverse("vite-development-generation")
    finally:
        reload(application_urls)
        clear_url_caches()
