"""Regenerate or verify the canonical, byte-stable OpenAPI artifact."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.core.management.base import CommandParser


class Command(BaseCommand):
    help = "Export OpenAPI.yaml; verify freshness and optional SDK source provenance."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--output", type=Path, default=Path(settings.BASE_DIR) / "OpenAPI.yaml"
        )
        parser.add_argument("--check", action="store_true")
        parser.add_argument(
            "--compare-source",
            type=Path,
            help="Require the fresh export SHA-256 to match SDK openapi-source.json.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        destination: Path = options["output"]
        source: Path | None = options["compare_source"]
        source_digest: str | None = (
            self.read_source_digest(source) if source is not None else None
        )
        with TemporaryDirectory(prefix="speleodb-openapi-") as directory:
            temporary = Path(directory) / "OpenAPI.yaml"
            call_command(
                "spectacular",
                format="openapi",
                file=str(temporary),
                validate=True,
                fail_on_warn=True,
                lang="en",
            )
            generated = temporary.read_bytes()
        digest: str = hashlib.sha256(generated).hexdigest()
        if options["check"]:
            if not destination.is_file() or destination.read_bytes() != generated:
                raise CommandError(
                    f"{destination} differs from the backend. "
                    "Run python manage.py export_api_schema and update @speleodb/api."
                )
        if source_digest is not None and source_digest != digest:
            raise CommandError(
                f"OpenAPI SHA-256 differs from SDK source record {source}: "
                f"generated {digest}, recorded {source_digest}. "
                "Review the canonical backend export, update the SDK source pin, "
                "and regenerate the SDK."
            )
        if not options["check"]:
            destination.write_bytes(generated)
        self.stdout.write(f"OpenAPI SHA-256: {digest}")

    @staticmethod
    def read_source_digest(source: Path) -> str:
        try:
            record: object = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CommandError(
                f"Cannot read SDK source record {source}: {error}"
            ) from error
        if not isinstance(record, dict):
            raise CommandError(f"SDK source record {source} must be a JSON object.")
        digest: object = record.get("sha256")
        revision: object = record.get("revision")
        if (
            not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or "revision" not in record
            or (
                revision is not None
                and (
                    not isinstance(revision, str)
                    or re.fullmatch(r"[0-9a-f]{40}", revision) is None
                )
            )
        ):
            raise CommandError(
                f"Invalid SDK source record {source}: expected a lowercase SHA-256 "
                "and a full lowercase backend commit revision, or null for "
                "unpublished development."
            )
        return digest
