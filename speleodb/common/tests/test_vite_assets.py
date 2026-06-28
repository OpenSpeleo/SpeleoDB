from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.template import Context
from django.template import Template
from django.test import override_settings

from speleodb.common.templatetags.vite_assets import reset_vite_asset_caches

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture(autouse=True)
def reset_caches() -> Generator[None]:
    reset_vite_asset_caches()
    yield
    reset_vite_asset_caches()


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    path = tmp_path / "entries.json"
    path.write_text(
        json.dumps(
            {
                "styles": {
                    "style-app": "tailwind_css/style.css",
                    "style-copy": "frontend_common/copy.css",
                },
                "scripts": {
                    "app": "frontend_common/app.js",
                    "controller-map": "frontend_common/controllers/map.js",
                },
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def manifest(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.json"
    payload: dict[str, dict[str, str | bool | list[str]]] = {
        "_shared.js": {
            "file": "assets/chunks/shared-111.js",
            "name": "shared",
        },
        "frontend_common/app.js": {
            "file": "assets/app-222.js",
            "name": "app",
            "isEntry": True,
            "imports": ["_shared.js"],
            "dynamicImports": ["frontend_common/controllers/map.js"],
        },
        "frontend_common/controllers/map.js": {
            "file": "assets/controller-map-333.js",
            "name": "controller-map",
            "isEntry": True,
            "imports": ["_shared.js"],
            "dynamicImports": ["_map.js"],
        },
        "_map.js": {
            "file": "assets/chunks/map-444.js",
            "name": "map",
        },
        "tailwind_css/style.css": {
            "file": "assets/style-app-555.css",
            "name": "style-app",
            "isEntry": True,
        },
        "frontend_common/copy.css": {
            "file": "assets/style-app-555.css",
            "name": "style-app",
            "names": ["style-app.css", "style-copy.css"],
            "isEntry": True,
        },
    }
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    for entry in payload.values():
        built_file = tmp_path / str(entry["file"])
        built_file.parent.mkdir(parents=True, exist_ok=True)
        built_file.touch()
    return path


def render(source: str) -> str:
    return Template(source).render(Context())


def test_renders_hashed_styles_script_and_recursive_preloads(
    registry: Path, manifest: Path
) -> None:
    with override_settings(
        VITE_ENTRY_REGISTRY_PATH=registry,
        VITE_MANIFEST_PATH=manifest,
        VITE_ASSET_ROOT=manifest.parent,
        VITE_ALLOW_MISSING_MANIFEST=False,
        STATIC_URL="/static/",
    ):
        html = render(
            "{% load vite_assets %}"
            "{% vite_styles 'style-app' %}"
            "{% vite_preload 'app' 'controller-map' %}"
            "{% vite_script 'app' %}"
        )

    assert "speleodb/vite/assets/style-app-555.css" in html
    assert html.count("assets/chunks/shared-111.js") == 1
    assert "assets/chunks/map-444.js" in html
    assert "assets/controller-map-333.js" in html
    assert "assets/app-222.js" in html
    assert html.count('type="module"') == 1


def test_app_preload_does_not_eagerly_fetch_dynamic_controllers(
    registry: Path, manifest: Path
) -> None:
    with override_settings(
        VITE_ENTRY_REGISTRY_PATH=registry,
        VITE_MANIFEST_PATH=manifest,
        VITE_ASSET_ROOT=manifest.parent,
        VITE_ALLOW_MISSING_MANIFEST=False,
    ):
        html = render("{% load vite_assets %}{% vite_preload 'app' %}")

    assert "shared-111.js" in html
    assert "controller-map-333.js" not in html
    assert "map-444.js" not in html


def test_resolves_vite_deduplicated_css_by_registry_source(
    registry: Path, manifest: Path
) -> None:
    with override_settings(
        VITE_ENTRY_REGISTRY_PATH=registry,
        VITE_MANIFEST_PATH=manifest,
        VITE_ASSET_ROOT=manifest.parent,
        VITE_ALLOW_MISSING_MANIFEST=False,
    ):
        html = render("{% load vite_assets %}{% vite_styles 'style-copy' %}")

    assert "assets/style-app-555.css" in html


def test_production_rejects_manifest_with_missing_asset(
    registry: Path, manifest: Path
) -> None:
    (manifest.parent / "assets/app-222.js").unlink()

    with (
        override_settings(
            VITE_ENTRY_REGISTRY_PATH=registry,
            VITE_MANIFEST_PATH=manifest,
            VITE_ASSET_ROOT=manifest.parent,
            VITE_ALLOW_MISSING_MANIFEST=False,
        ),
        pytest.raises(ImproperlyConfigured, match="missing asset"),
    ):
        render("{% load vite_assets %}{% vite_script 'app' %}")


def test_debug_fallback_uses_stable_registry_names(
    registry: Path, tmp_path: Path
) -> None:
    with override_settings(
        VITE_ENTRY_REGISTRY_PATH=registry,
        VITE_MANIFEST_PATH=tmp_path / "missing.json",
        VITE_ALLOW_MISSING_MANIFEST=True,
        STATIC_URL="/static/",
    ):
        html = render(
            "{% load vite_assets %}"
            "{% vite_styles 'style-app' %}"
            "{% vite_preload 'controller-map' %}"
            "{% vite_script 'app' %}"
        )

    assert "assets/style-app.css" in html
    assert "assets/controller-map.js" in html
    assert "assets/app.js" in html


def test_missing_production_manifest_fails(registry: Path, tmp_path: Path) -> None:
    with (
        override_settings(
            VITE_ENTRY_REGISTRY_PATH=registry,
            VITE_MANIFEST_PATH=tmp_path / "missing.json",
            VITE_ALLOW_MISSING_MANIFEST=False,
        ),
        pytest.raises(ImproperlyConfigured, match="run npm run build"),
    ):
        render("{% load vite_assets %}{% vite_script 'app' %}")


def test_unknown_and_wrong_type_entries_fail(registry: Path, manifest: Path) -> None:
    with override_settings(
        VITE_ENTRY_REGISTRY_PATH=registry,
        VITE_MANIFEST_PATH=manifest,
        VITE_ALLOW_MISSING_MANIFEST=False,
    ):
        with pytest.raises(ImproperlyConfigured, match="Unknown Vite logical entry"):
            render("{% load vite_assets %}{% vite_script 'missing' %}")
        with pytest.raises(ImproperlyConfigured, match="not a script"):
            render("{% load vite_assets %}{% vite_script 'style-app' %}")


def test_manifest_rejects_unsafe_paths(registry: Path, manifest: Path) -> None:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["frontend_common/app.js"]["file"] = "../secret.js"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with (
        override_settings(
            VITE_ENTRY_REGISTRY_PATH=registry,
            VITE_MANIFEST_PATH=manifest,
            VITE_ALLOW_MISSING_MANIFEST=False,
        ),
        pytest.raises(ImproperlyConfigured, match="Unsafe Vite manifest"),
    ):
        render("{% load vite_assets %}{% vite_script 'app' %}")
