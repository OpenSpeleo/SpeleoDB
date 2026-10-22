"""Exercise real local export freshness through the command API."""

from __future__ import annotations

from hashlib import sha256
from io import StringIO
from typing import TYPE_CHECKING

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import path
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.settings import spectacular_settings

from speleodb.api.v2.views.user import UserAutocompleteView

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import Settings


MAX_SCHEMA_BYTES: int = 100_000
urlpatterns = [path("api/v2/users/autocomplete/", UserAutocompleteView.as_view())]


@pytest.fixture(autouse=True)
def small_schema(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    # File freshness needs real schema generation, but only one real endpoint.
    # test_swagger.py separately validates the complete application generator,
    # including its auth and protocol schemas.
    settings.ROOT_URLCONF = __name__
    monkeypatch.setattr(
        spectacular_settings, "DEFAULT_GENERATOR_CLASS", SchemaGenerator
    )


@pytest.fixture
def exported_schema(tmp_path: Path) -> bytes:
    destination = tmp_path / "expected.yaml"
    call_command("export_api_schema", "--output", str(destination), stdout=StringIO())
    generated = destination.read_bytes()
    assert b"v2_user_autocomplete_list" in generated
    assert len(generated) <= MAX_SCHEMA_BYTES
    return generated


def test_fresh_export_is_checked_without_rewriting(
    tmp_path: Path, exported_schema: bytes
) -> None:
    destination: Path = tmp_path / "OpenAPI.yaml"
    destination.write_bytes(exported_schema)
    original_modified: int = destination.stat().st_mtime_ns
    output: StringIO = StringIO()

    call_command(
        "export_api_schema",
        "--output",
        str(destination),
        "--check",
        stdout=output,
    )

    assert destination.read_bytes() == exported_schema
    assert destination.stat().st_mtime_ns == original_modified
    assert (
        output.getvalue() == f"OpenAPI SHA-256: {sha256(exported_schema).hexdigest()}\n"
    )


def test_check_rejects_stale_export_without_rewriting(
    tmp_path: Path, exported_schema: bytes
) -> None:
    destination: Path = tmp_path / "OpenAPI.yaml"
    stale: bytes = exported_schema + b"\n"
    destination.write_bytes(stale)

    with pytest.raises(CommandError, match="differs from the backend"):
        call_command(
            "export_api_schema",
            "--output",
            str(destination),
            "--check",
            stdout=StringIO(),
        )

    assert destination.read_bytes() == stale


def test_check_rejects_missing_export_without_creating_it(tmp_path: Path) -> None:
    destination: Path = tmp_path / "OpenAPI.yaml"

    with pytest.raises(CommandError, match="differs from the backend"):
        call_command(
            "export_api_schema",
            "--output",
            str(destination),
            "--check",
            stdout=StringIO(),
        )

    assert not destination.exists()


@pytest.mark.parametrize("existing", [False, True])
def test_export_writes_fresh_bytes(
    tmp_path: Path, exported_schema: bytes, existing: bool
) -> None:
    destination: Path = tmp_path / "OpenAPI.yaml"
    if existing:
        destination.write_bytes(b"stale export")
    output: StringIO = StringIO()

    call_command(
        "export_api_schema",
        "--output",
        str(destination),
        stdout=output,
    )

    assert destination.read_bytes() == exported_schema
    assert (
        output.getvalue() == f"OpenAPI SHA-256: {sha256(exported_schema).hexdigest()}\n"
    )
