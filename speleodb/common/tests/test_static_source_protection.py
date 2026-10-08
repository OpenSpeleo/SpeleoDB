from __future__ import annotations

import json
from dataclasses import dataclass
from http import HTTPStatus
from http.client import HTTPConnection
from http.client import HTTPResponse
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import pytest
from django.apps import AppConfig
from django.apps import apps
from django.conf import settings
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.apps import StaticFilesConfig
from django.contrib.staticfiles.views import serve
from django.core.management import call_command
from django.http import FileResponse
from django.test import Client
from django.test import override_settings
from django.urls import path

from speleodb.common.staticfiles import CompiledStaticFilesConfig
from speleodb.common.staticfiles import SourceProtectedAppDirectoriesFinder
from speleodb.common.staticfiles import SourceProtectedFileSystemFinder

if TYPE_CHECKING:
    from collections.abc import Generator
    from urllib.parse import SplitResult

    from pytest_django.fixtures import Settings
    from pytest_django.live_server_helper import LiveServer

    from speleodb.common.templatetags.vite_assets import ManifestEntry


FINDERS = [
    "speleodb.common.staticfiles.SourceProtectedFileSystemFinder",
    "speleodb.common.staticfiles.SourceProtectedAppDirectoriesFinder",
]
SOURCE_FILES = ("source.ts", "contract.d.ts", "nested/worker.ts")
DELIVERED_FILES = (
    "speleodb/vite/assets/app-123.js",
    "speleodb/vite/assets/worker-456.js",
    "private/ts/vendors/library.js",
    "style.css",
)
urlpatterns = [path("static/<path:path>", serve)]


class StaticSourceTestApp(AppConfig):
    name = "speleodb.common.tests"
    label = "static_source_test"


@dataclass(frozen=True)
class StaticLocations:
    collected: Path
    sources: tuple[Path, ...]


@pytest.fixture
def static_locations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[StaticLocations]:
    extra = tmp_path / "extra"
    prefixed = tmp_path / "prefixed"
    app = tmp_path / "application"
    app_static = app / "static"
    collected = tmp_path / "collected"
    for directory in (extra, prefixed, app_static):
        for filename in (*SOURCE_FILES, *DELIVERED_FILES):
            target = directory / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"fixture: {filename}", encoding="utf-8")

    monkeypatch.setattr(StaticSourceTestApp, "path", str(app), raising=False)
    with override_settings(
        INSTALLED_APPS=[
            "speleodb.common.staticfiles.CompiledStaticFilesConfig",
            f"{__name__}.StaticSourceTestApp",
        ],
        STATICFILES_FINDERS=FINDERS,
        STATICFILES_DIRS=[str(extra), ("prefixed", str(prefixed))],
        STATIC_ROOT=str(collected),
        STATIC_URL="/static/",
        STORAGES={
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        },
        ROOT_URLCONF=__name__,
        MIDDLEWARE=[],
        DEBUG=True,
        ALLOWED_HOSTS=["testserver"],
    ):
        yield StaticLocations(collected, (extra, prefixed, app_static))


def test_application_configures_both_source_protected_finders() -> None:
    assert settings.STATICFILES_FINDERS == FINDERS
    assert isinstance(apps.get_app_config("staticfiles"), CompiledStaticFilesConfig)
    assert CompiledStaticFilesConfig.ignore_patterns == [
        *StaticFilesConfig.ignore_patterns,
        "*.ts",
    ]


@pytest.fixture
def live_server(request: pytest.FixtureRequest, settings: Settings) -> LiveServer:
    # CI starts with a CDN URL; set it before the server captures its static URL.
    settings.STATIC_URL = "https://assets.example.test/staticfiles/"
    server: LiveServer = request.getfixturevalue("live_server")
    return server


@pytest.mark.django_db(transaction=True)
def test_live_server_delivers_collected_assets_and_rejects_sources(
    live_server: LiveServer,
) -> None:
    manifest: dict[str, ManifestEntry] = json.loads(
        Path(settings.VITE_MANIFEST_PATH).read_text(encoding="utf-8")
    )
    asset: str = manifest["frontend_common/app.ts"]["file"]
    source: Path = (
        Path(settings.BASE_DIR)
        / "frontend_private/static/private/ts/map_viewer/main.ts"
    )
    assert source.is_file()
    assert not list(Path(settings.STATIC_ROOT).rglob("*.ts"))
    address: SplitResult = urlsplit(live_server.url)
    assert address.scheme == "http"
    assert address.hostname is not None
    connection: HTTPConnection = HTTPConnection(
        address.hostname, address.port, timeout=10
    )
    response: HTTPResponse
    try:
        connection.request("GET", f"/static/speleodb/vite/{asset}")
        response = connection.getresponse()
        assert response.status == HTTPStatus.OK
        assert response.read() == (Path(settings.VITE_ASSET_ROOT) / asset).read_bytes()
        connection.request("GET", "/static/ts/vendors/jquery-3.7.1.js")
        response = connection.getresponse()
        assert response.status == HTTPStatus.OK
        assert response.read()
        connection.request("GET", "/static/private/ts/map_viewer/main.ts")
        response = connection.getresponse()
        assert response.status == HTTPStatus.NOT_FOUND
        response.read()
    finally:
        connection.close()


@pytest.mark.parametrize("filename", SOURCE_FILES)
def test_sources_are_hidden_from_each_finder_and_both_lookup_modes(
    static_locations: StaticLocations, filename: str
) -> None:
    assert all(
        (directory / filename).is_file() for directory in static_locations.sources
    )
    for finder in finders.get_finders():
        assert isinstance(
            finder,
            SourceProtectedFileSystemFinder | SourceProtectedAppDirectoriesFinder,
        )
        assert not finder.find(filename)
        assert finder.find(filename, find_all=True) == []
    assert finders.find(filename) is None
    assert finders.find(filename, find_all=True) == []
    assert finders.find(f"prefixed/{filename}") is None
    assert finders.find(f"prefixed/{filename}", find_all=True) == []


def test_finder_listing_preserves_storage_and_ignore_patterns(
    static_locations: StaticLocations,
) -> None:
    for finder in finders.get_finders():
        entries = list(
            finder.list([*CompiledStaticFilesConfig.ignore_patterns, "*.css"])
        )
        assert entries
        assert {name for name, _storage in entries} == set(DELIVERED_FILES) - {
            "style.css"
        }
        for name, storage in entries:
            assert storage.exists(name)
    assert not static_locations.collected.exists()


@pytest.mark.parametrize("filename", SOURCE_FILES)
def test_static_view_returns_404_for_typescript_sources(
    static_locations: StaticLocations, filename: str
) -> None:
    client = Client()
    assert client.get(f"/static/{filename}").status_code == HTTPStatus.NOT_FOUND
    assert (
        client.get(f"/static/prefixed/{filename}").status_code == HTTPStatus.NOT_FOUND
    )
    assert not static_locations.collected.exists()


@pytest.mark.parametrize("filename", DELIVERED_FILES)
def test_emitted_scripts_workers_vendors_and_styles_remain_deliverable(
    static_locations: StaticLocations, filename: str
) -> None:
    assert finders.find(filename) == str(static_locations.sources[0] / filename)
    assert finders.find(filename, find_all=True) == [
        str(static_locations.sources[0] / filename),
        str(static_locations.sources[2] / filename),
    ]
    assert finders.find(f"prefixed/{filename}") == str(
        static_locations.sources[1] / filename
    )
    client = Client()
    response = client.get(f"/static/{filename}")
    assert response.status_code == HTTPStatus.OK
    assert isinstance(response, FileResponse)
    # Exhaust Django's test-client wrapper so it closes the file without
    # closing the surrounding test transaction's database connection.
    assert b"".join(response) == f"fixture: {filename}".encode()
    assert response.closed


@pytest.mark.parametrize(
    "finder_paths",
    [
        FINDERS,
        [
            "django.contrib.staticfiles.finders.FileSystemFinder",
            "django.contrib.staticfiles.finders.AppDirectoriesFinder",
        ],
    ],
    ids=["source-lookup-guards", "standard-django-finders"],
)
def test_collectstatic_excludes_sources_but_retains_generated_and_vendor_assets(
    static_locations: StaticLocations, finder_paths: list[str]
) -> None:
    with override_settings(STATICFILES_FINDERS=finder_paths):
        call_command("collectstatic", interactive=False, verbosity=0, stdout=StringIO())
    collected = {
        str(filename.relative_to(static_locations.collected))
        for filename in static_locations.collected.rglob("*")
        if filename.is_file()
    }
    assert collected == set(DELIVERED_FILES) | {
        f"prefixed/{filename}" for filename in DELIVERED_FILES
    }
