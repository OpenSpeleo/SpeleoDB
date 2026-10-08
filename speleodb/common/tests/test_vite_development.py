from __future__ import annotations

from importlib import reload

import pytest
from django.template import Context
from django.template import Template
from django.test import override_settings
from django.urls import NoReverseMatch
from django.urls import Resolver404
from django.urls import clear_url_caches
from django.urls import resolve
from django.urls import reverse

from config import urls as application_urls
from speleodb.common.management.commands.dump_url_config import collect_and_filter_urls
from speleodb.common.templatetags import vite_assets


@pytest.mark.parametrize("debug", [True, False])
@pytest.mark.parametrize(
    "asset_file", ["assets/app-manual.js", "assets/dev/session-a/2/app.js"]
)
def test_manual_assets_never_emit_reload_attributes(
    monkeypatch: pytest.MonkeyPatch, debug: bool, asset_file: str
) -> None:
    manifest: dict[str, vite_assets.ManifestEntry] = {
        "app.ts": {"file": asset_file, "isEntry": True},
    }
    registry: vite_assets.EntryRegistry = {
        "scripts": {"app": "app.ts"},
        "styles": {},
    }
    monkeypatch.setattr(vite_assets, "_manifest", lambda: manifest)
    monkeypatch.setattr(vite_assets, "_entry_registry", lambda: registry)
    template: Template = Template("{% load vite_assets %}{% vite_script 'app' %}")
    with override_settings(
        DEBUG=debug, VITE_ALLOW_MISSING_MANIFEST=True, STATIC_URL="/static/"
    ):
        html: str = template.render(Context())

    assert html == (
        f'<script type="module" src="/static/speleodb/vite/{asset_file}" '
        "crossorigin></script>"
    )
    assert "data-speleodb-generation" not in html
    assert "data-speleodb-reload" not in html


@pytest.mark.parametrize("debug", [True, False])
def test_reload_route_is_absent_even_in_debug(debug: bool) -> None:
    try:
        with override_settings(DEBUG=debug, ROOT_URLCONF="config.urls"):
            reload(application_urls)
            clear_url_caches()
            with pytest.raises(NoReverseMatch):
                reverse("vite-development-generation")
            with pytest.raises(Resolver404):
                resolve("/__assets__/generation/")
            assert not any(
                route["url"].startswith("/__assets__/")
                for route in collect_and_filter_urls()
            )
    finally:
        reload(application_urls)
        clear_url_caches()
