"""Exercise real export freshness and SDK provenance through the command API."""

from __future__ import annotations

import json
from hashlib import sha256
from io import StringIO
from typing import TYPE_CHECKING

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(scope="module")
def exported_schema(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    destination = tmp_path_factory.mktemp("schema-export") / "OpenAPI.yaml"
    call_command("export_api_schema", "--output", str(destination), stdout=StringIO())
    return destination.read_bytes()


def write_source_record(
    path: Path, content: bytes, *, revision: str | None = None
) -> None:
    path.write_text(
        json.dumps({"revision": revision, "sha256": sha256(content).hexdigest()}),
        encoding="utf-8",
    )


@pytest.mark.parametrize("revision", [None, "a" * 40])
def test_fresh_export_matches_source_digest_without_rewriting(
    tmp_path: Path, exported_schema: bytes, revision: str | None
) -> None:
    destination = tmp_path / "OpenAPI.yaml"
    destination.write_bytes(exported_schema)
    source = tmp_path / "openapi-source.json"
    write_source_record(source, exported_schema, revision=revision)
    original_record = source.read_bytes()
    output = StringIO()

    call_command(
        "export_api_schema",
        "--output",
        str(destination),
        "--check",
        "--compare-source",
        str(source),
        stdout=output,
    )

    assert destination.read_bytes() == exported_schema
    assert source.read_bytes() == original_record
    assert (
        output.getvalue() == f"OpenAPI SHA-256: {sha256(exported_schema).hexdigest()}\n"
    )


def test_digest_comparison_uses_fresh_export_and_preserves_output_on_failure(
    tmp_path: Path, exported_schema: bytes
) -> None:
    destination = tmp_path / "OpenAPI.yaml"
    stale = exported_schema + b"\n"
    destination.write_bytes(stale)
    source = tmp_path / "openapi-source.json"
    write_source_record(source, stale)
    original_record = source.read_bytes()

    with pytest.raises(CommandError, match="SHA-256 differs from SDK source record"):
        call_command(
            "export_api_schema",
            "--output",
            str(destination),
            "--compare-source",
            str(source),
            stdout=StringIO(),
        )

    assert destination.read_bytes() == stale
    assert source.read_bytes() == original_record


def test_check_rejects_stale_export_even_when_source_digest_matches_it(
    tmp_path: Path, exported_schema: bytes
) -> None:
    destination = tmp_path / "OpenAPI.yaml"
    stale = exported_schema + b"\n"
    destination.write_bytes(stale)
    source = tmp_path / "openapi-source.json"
    write_source_record(source, stale)

    with pytest.raises(CommandError, match="differs from the backend"):
        call_command(
            "export_api_schema",
            "--output",
            str(destination),
            "--check",
            "--compare-source",
            str(source),
            stdout=StringIO(),
        )

    assert destination.read_bytes() == stale


def test_regeneration_writes_fresh_bytes_only_after_source_digest_matches(
    tmp_path: Path, exported_schema: bytes
) -> None:
    destination = tmp_path / "OpenAPI.yaml"
    destination.write_bytes(b"stale export")
    source = tmp_path / "openapi-source.json"
    write_source_record(source, exported_schema)

    call_command(
        "export_api_schema",
        "--output",
        str(destination),
        "--compare-source",
        str(source),
        stdout=StringIO(),
    )

    assert destination.read_bytes() == exported_schema


@pytest.mark.parametrize(
    "record",
    [
        None,
        [],
        {"revision": None},
        {"sha256": "a" * 64},
        {"revision": None, "sha256": "A" * 64},
        {"revision": None, "sha256": "a" * 63},
        {"revision": None, "sha256": 123},
        {"revision": "master", "sha256": "a" * 64},
        {"revision": "A" * 40, "sha256": "a" * 64},
        {"revision": False, "sha256": "a" * 64},
    ],
)
def test_invalid_source_records_fail_without_creating_an_export(
    tmp_path: Path, record: object
) -> None:
    source = tmp_path / "openapi-source.json"
    source.write_text(json.dumps(record), encoding="utf-8")
    destination = tmp_path / "OpenAPI.yaml"

    with pytest.raises(CommandError, match="SDK source record"):
        call_command(
            "export_api_schema",
            "--output",
            str(destination),
            "--compare-source",
            str(source),
            stdout=StringIO(),
        )

    assert not destination.exists()


@pytest.mark.parametrize("content", [None, b"{", b"\xff"])
def test_unreadable_source_records_fail_without_creating_an_export(
    tmp_path: Path, content: bytes | None
) -> None:
    source = tmp_path / "openapi-source.json"
    if content is not None:
        source.write_bytes(content)
    destination = tmp_path / "OpenAPI.yaml"

    with pytest.raises(CommandError, match="Cannot read SDK source record"):
        call_command(
            "export_api_schema",
            "--output",
            str(destination),
            "--compare-source",
            str(source),
            stdout=StringIO(),
        )

    assert not destination.exists()
