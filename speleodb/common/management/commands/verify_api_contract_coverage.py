"""Require observed HTTP evidence for every operation in the composed contract."""

from __future__ import annotations

import json
from hashlib import sha256
from http import HTTPStatus
from pathlib import Path
from typing import Any

import yaml
from allauth.account import app_settings as account_settings
from allauth.headless import app_settings as headless_settings
from allauth.headless.tokens.strategies.sessions import SessionTokenStrategy
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.core.management.base import CommandParser

from speleodb.api.schema import HTTP_METHODS
from speleodb.api.schema_inventory import current_api_routes
from speleodb.testing.api_contract import is_successful_observation

REPORT_FORMAT_VERSION = 2


def read_contract_report(report: Path) -> dict[str, Any]:
    data = json.loads(report.read_text())
    if (
        not isinstance(data, dict)
        or data.get("format_version") != REPORT_FORMAT_VERSION
    ):
        raise CommandError(f"{report} is missing versioned schema provenance")
    if data.get("exit_status") != 0:
        raise CommandError(f"{report} is not from a passing pytest session")
    return data


def disabled_operation_reason(path: str) -> str | None:
    if not path.startswith(("/_allauth/", "/api/auth/")):
        return None
    if "/phone" in path and "phone" not in account_settings.SIGNUP_FIELDS:
        return "Phone authentication is not configured (ACCOUNT_SIGNUP_FIELDS)."
    if (
        path.endswith("/auth/code/confirm")
        and not account_settings.LOGIN_BY_CODE_ENABLED
    ):
        return "ACCOUNT_LOGIN_BY_CODE_ENABLED is false."
    if (
        path.endswith("/auth/email/verify/resend")
        and not account_settings.EMAIL_VERIFICATION_BY_CODE_ENABLED
    ):
        return "ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED is false."
    if (
        path.endswith("/tokens/refresh")
        and type(headless_settings.TOKEN_STRATEGY) is SessionTokenStrategy
    ):
        return "Configured SessionTokenStrategy does not issue refresh tokens."
    return None


def is_completed_auth_transition(item: dict[str, Any]) -> bool:
    """These tests assert actual account effects as well as expected 401 flows."""
    return item["status"] == HTTPStatus.UNAUTHORIZED and (
        "test_configured_account_lifecycle" in item["test"]
        and item["operation_id"].startswith("auth_")
    )


class Command(BaseCommand):
    help = "Verify operation coverage from passing --api-contract-report pytest runs."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("reports", nargs="+", type=Path)
        parser.add_argument(
            "--write", action="store_true", help="Update durable evidence registry"
        )
        parser.add_argument(
            "--output",
            type=Path,
            default=settings.BASE_DIR / "docs/api-contract-coverage.json",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        observations: list[dict[str, Any]] = []
        provenance: list[dict[str, Any]] = []
        exported: bytes = (settings.BASE_DIR / "OpenAPI.yaml").read_bytes()
        current_hash: str = sha256(exported).hexdigest()
        for report in options["reports"]:
            data = read_contract_report(report)
            if data.get("schema_sha256") != current_hash:
                raise CommandError(
                    f"{report} does not validate the current schema snapshot"
                )
            provenance.append(
                {
                    "report": report.name,
                    "exit_status": data["exit_status"],
                    "test_invocation": data["test_invocation"],
                    "provenance": data.get("provenance", "Captured by test observer"),
                }
            )
            observations.extend(data["observations"])
        violations = [item for item in observations if "error" in item]
        if violations:
            raise CommandError(f"Reports contain {len(violations)} contract violations")
        document: dict[str, Any] = yaml.safe_load(exported)
        operations = {
            operation["operationId"]: (path, method)
            for path, item in document["paths"].items()
            for method, operation in item.items()
            if method in HTTP_METHODS
        }
        unknown = {item["operation_id"] for item in observations} - operations.keys()
        if unknown:
            raise CommandError(f"Reports contain unknown operations: {sorted(unknown)}")
        evidence: dict[str, Any] = {}
        missing: list[str] = []
        for identifier, (path, method) in sorted(operations.items()):
            observed = [
                item for item in observations if item["operation_id"] == identifier
            ]
            successful = [item for item in observed if is_successful_observation(item)]
            transitions = [
                item for item in observed if is_completed_auth_transition(item)
            ]
            disabled = disabled_operation_reason(path)
            if not observed or not (successful or transitions or disabled):
                missing.append(identifier)
            branches = sorted(
                {
                    (item["status"], item.get("media_type", "unrecorded"))
                    for item in observed
                }
            )
            declared = document["paths"][path][method]["responses"]
            evidence[identifier] = {
                "method": method.upper(),
                "path": path,
                "observed_response_branches": [
                    {"status": code, "media_type": media} for code, media in branches
                ],
                "unobserved_declared_statuses": sorted(
                    set(declared) - {str(item["status"]) for item in observed}
                ),
                "successful_response_observed": bool(successful),
                "protocol_rejections_observed": sum(
                    bool(item.get("protocol_error")) for item in observed
                ),
                "completed_auth_transition_observed": bool(transitions),
                "configured_unavailable_reason": disabled,
                "request_parameters_validated": any(
                    item.get("request_parameters_validated") for item in observed
                ),
                "request_body_validated": any(
                    item.get("request_body_validated") for item in observed
                ),
                "undocumented_request_fields": sorted(
                    {
                        field
                        for item in observed
                        for field in item.get("undocumented_request_fields", [])
                    }
                ),
                "tests": sorted(
                    {
                        item["test"].split("[", 1)[0].removesuffix(" (call)")
                        for item in observed
                    }
                ),
            }
        result = {
            "format_version": 3,
            "schema_sha256": current_hash,
            "source_reports": provenance,
            "canonical_operations": len(operations),
            "resolver_operations": len(current_api_routes()),
            "alias_operations": sum(
                path.startswith("/api/auth/") for path, _ in operations.values()
            ),
            "scope": (
                "Supported machine APIs: v2, both authentication mounts, "
                "health, Git smart HTTP, well-known discovery and schema export. "
                "Each mount requires its own observed HTTP evidence. "
                "Obsolete SpeleoDB /api/v1 is excluded."
            ),
            "evidence": (
                "Rendered response validation; parameters and bounded "
                "JSON/form requests on successful calls. Multipart files are "
                "exercised by integration tests; their raw request bodies are "
                "not revalidated by the observer."
            ),
            "operations": evidence,
        }
        if missing:
            raise CommandError(
                "Operations lack successful/transition/configuration evidence: "
                + ", ".join(missing)
            )
        if options["write"]:
            options["output"].write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n"
            )
        self.stdout.write(
            f"Validated observed coverage of {len(operations)} canonical operations"
        )
