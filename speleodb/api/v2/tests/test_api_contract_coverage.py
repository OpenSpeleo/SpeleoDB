"""Older observations can be reused only when their effective contract is unchanged."""

from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from hashlib import sha256
from typing import TYPE_CHECKING
from typing import Any

import pytest
from django.core.management.base import CommandError

from speleodb.common.management.commands.verify_api_contract_coverage import (
    expanded_schema,
)
from speleodb.common.management.commands.verify_api_contract_coverage import (
    operation_contract,
)
from speleodb.common.management.commands.verify_api_contract_coverage import (
    read_contract_report,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "change", ["server", "security", "scheme", "parameter", "path_server"]
)
def test_inherited_contract_changes_invalidate_previous_evidence(change: str) -> None:
    original: dict[str, Any] = {
        "openapi": "3.0.3",
        "servers": [{"url": "/"}],
        "security": [{"token": []}],
        "components": {
            "securitySchemes": {"token": {"type": "http", "scheme": "bearer"}}
        },
        "paths": {"/items": {"get": {"responses": {"200": {"description": "OK"}}}}},
    }
    modified = deepcopy(original)
    match change:
        case "server":
            modified["servers"][0]["url"] = "/new"
        case "security":
            modified["security"] = []
        case "scheme":
            modified["components"]["securitySchemes"]["token"]["scheme"] = "basic"
        case "parameter":
            modified["paths"]["/items"]["parameters"] = [
                {
                    "name": "version",
                    "in": "query",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ]
        case "path_server":
            modified["paths"]["/items"]["servers"] = [{"url": "/new"}]
    assert operation_contract(original, "/items", "get") != operation_contract(
        modified, "/items", "get"
    )


def test_reference_comparison_decodes_json_pointer_and_rejects_external_refs() -> None:
    document = {"components": {"schemas": {"some/name~": {"type": "integer"}}}}
    assert expanded_schema({"$ref": "#/components/schemas/some~1name~0"}, document) == {
        "resolved_reference": {"type": "integer"}
    }
    with pytest.raises(CommandError, match="local OpenAPI references"):
        expanded_schema({"$ref": "https://example.invalid/schema.json"}, document)


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
