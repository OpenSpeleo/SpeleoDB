"""Durable evidence combines only passing reports for the exact current schema."""

from __future__ import annotations

import json
import subprocess
import sys
from hashlib import sha256
from io import StringIO
from typing import TYPE_CHECKING
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from speleodb.common.management.commands.verify_api_contract_coverage import (
    read_contract_report,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import Settings


@pytest.fixture
def coverage_snapshot(tmp_path: Path, settings: Settings) -> bytes:
    settings.BASE_DIR = tmp_path
    document: dict[str, Any] = {
        "openapi": "3.0.3",
        "info": {"title": "Coverage fixture", "version": "1"},
        "paths": {
            "/items/": {
                "get": {
                    "operationId": "items_list",
                    "responses": {
                        status: {"description": status}
                        for status in ("200", "403", "404")
                    },
                },
                "post": {
                    "operationId": "items_create",
                    "responses": {
                        status: {"description": status} for status in ("201", "400")
                    },
                },
            }
        },
    }
    exported: bytes = json.dumps(document).encode()
    (tmp_path / "OpenAPI.yaml").write_bytes(exported)
    return exported


def write_report(
    destination: Path,
    exported: bytes,
    observations: list[dict[str, Any]],
) -> Path:
    destination.write_text(
        json.dumps(
            {
                "format_version": 2,
                "schema_sha256": sha256(exported).hexdigest(),
                "exit_status": 0,
                "test_invocation": ["pytest", destination.stem],
                "provenance": "Observed test responses",
                "observations": observations,
            }
        )
    )
    return destination


def test_matching_reports_aggregate_evidence_with_one_schema_fingerprint(
    tmp_path: Path, coverage_snapshot: bytes
) -> None:
    first: Path = write_report(
        tmp_path / "first.json",
        coverage_snapshot,
        [
            {
                "operation_id": "items_list",
                "status": 200,
                "media_type": "application/json",
                "test": "test_list[allowed] (call)",
                "request_parameters_validated": True,
            },
            {
                "operation_id": "items_list",
                "status": 403,
                "media_type": "application/json",
                "test": "test_list[denied] (call)",
            },
        ],
    )
    second: Path = write_report(
        tmp_path / "second.json",
        coverage_snapshot,
        [
            {
                "operation_id": "items_create",
                "status": 201,
                "media_type": "application/json",
                "test": "test_create (call)",
                "request_body_validated": True,
            }
        ],
    )
    output: Path = tmp_path / "coverage.json"

    call_command(
        "verify_api_contract_coverage",
        str(first),
        str(second),
        "--write",
        "--output",
        str(output),
        stdout=StringIO(),
    )

    serialized: str = output.read_text()
    registry: dict[str, Any] = json.loads(serialized)
    fingerprint: str = sha256(coverage_snapshot).hexdigest()
    assert registry["format_version"] == 3  # noqa: PLR2004
    assert registry["schema_sha256"] == fingerprint
    assert serialized.count(fingerprint) == 1
    assert serialized.count('"schema_sha256"') == 1
    assert registry["source_reports"] == [
        {
            "report": "first.json",
            "exit_status": 0,
            "test_invocation": ["pytest", "first"],
            "provenance": "Observed test responses",
        },
        {
            "report": "second.json",
            "exit_status": 0,
            "test_invocation": ["pytest", "second"],
            "provenance": "Observed test responses",
        },
    ]
    assert set(registry["operations"]) == {"items_list", "items_create"}
    listed: dict[str, Any] = registry["operations"]["items_list"]
    assert listed["observed_response_branches"] == [
        {"status": 200, "media_type": "application/json"},
        {"status": 403, "media_type": "application/json"},
    ]
    assert listed["unobserved_declared_statuses"] == ["404"]
    assert listed["tests"] == ["test_list"]
    assert listed["request_parameters_validated"]
    assert listed["successful_response_observed"]
    created: dict[str, Any] = registry["operations"]["items_create"]
    assert created["observed_response_branches"] == [
        {"status": 201, "media_type": "application/json"}
    ]
    assert created["unobserved_declared_statuses"] == ["400"]
    assert created["tests"] == ["test_create"]
    assert created["request_body_validated"]
    assert created["successful_response_observed"]


@pytest.mark.parametrize(
    "reports", [("stale",), ("current", "stale"), ("stale", "current")]
)
def test_stale_reports_are_rejected_even_with_complete_current_evidence(
    tmp_path: Path, coverage_snapshot: bytes, reports: tuple[str, ...]
) -> None:
    observations: list[dict[str, Any]] = [
        {
            "operation_id": "items_list",
            "status": 200,
            "test": "test_list (call)",
        },
        {
            "operation_id": "items_create",
            "status": 201,
            "test": "test_create (call)",
        },
    ]
    for name, exported in (
        ("current", coverage_snapshot),
        ("stale", coverage_snapshot + b"\n"),
    ):
        write_report(tmp_path / f"{name}.json", exported, observations)
    output: Path = tmp_path / "coverage.json"
    output.write_text("existing registry")

    with pytest.raises(CommandError, match="does not validate the current schema"):
        call_command(
            "verify_api_contract_coverage",
            *(str(tmp_path / f"{name}.json") for name in reports),
            "--write",
            "--output",
            str(output),
            stdout=StringIO(),
        )

    assert output.read_text() == "existing registry"


@pytest.mark.parametrize("exit_status", [1, 2, None])
def test_failed_or_unverified_session_cannot_be_evidence(
    tmp_path: Path, exit_status: int | None
) -> None:
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"format_version": 2, "exit_status": exit_status}))
    with pytest.raises(CommandError, match="passing pytest session"):
        read_contract_report(report)


def test_observer_validates_the_exact_hashed_snapshot(tmp_path: Path) -> None:
    # This deliberately differs from the live application's generated schema.
    exported = b'openapi: "3.0.3"\npaths: {}\n'
    (tmp_path / "OpenAPI.yaml").write_bytes(exported)
    # A real child process owns its schema cache/metadata. The active suite's
    # observer must retain the provenance of its own canonical snapshot.
    program = """
import json
import sys
from pathlib import Path

import django
from django.test import override_settings

from speleodb.testing.api_contract import CONTRACT_METADATA
from speleodb.testing.api_contract import contract_schema

django.setup()
with override_settings(BASE_DIR=Path(sys.argv[1])):
    document = contract_schema()
print(json.dumps({"document": document, "metadata": CONTRACT_METADATA}))
"""
    result = subprocess.run(  # noqa: S603 - Fixed interpreter/program, private data path.
        [sys.executable, "-c", program, str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    observed = json.loads(result.stdout.splitlines()[-1])
    assert observed["document"] == {"openapi": "3.0.3", "paths": {}}
    assert observed["metadata"]["schema_sha256"] == sha256(exported).hexdigest()
