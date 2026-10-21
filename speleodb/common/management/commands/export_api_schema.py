"""Regenerate or verify the canonical, byte-stable OpenAPI artifact."""

from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.core.management.base import CommandParser


class Command(BaseCommand):
    help = "Export OpenAPI.yaml or verify freshness against the backend."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--output", type=Path, default=Path(settings.BASE_DIR) / "OpenAPI.yaml"
        )
        parser.add_argument("--check", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        destination: Path = options["output"]
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
                    "Run python manage.py export_api_schema."
                )
        if not options["check"]:
            destination.write_bytes(generated)
        self.stdout.write(f"OpenAPI SHA-256: {digest}")
