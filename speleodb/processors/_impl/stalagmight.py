# -*- coding: utf-8 -*-

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError

from speleodb.common.constants import STALAGMIGHT_FILENAME
from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import FileFormat

if TYPE_CHECKING:
    from speleodb.processors.artifact import Artifact


class StalagmightFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [".stalx"]
    ALLOWED_MIMETYPES = ["application/octet-stream", "application/vnd.sqlite3"]
    ASSOC_FILEFORMAT = FileFormat.STALAGMIGHT

    TARGET_FOLDER = None
    TARGET_SAVE_FILENAME: str = STALAGMIGHT_FILENAME
    TARGET_DOWNLOAD_FILENAME = "{project_name}__{timestamp}.stalx"

    def _add_to_project(self, artifact: Artifact) -> list[Path]:
        content = artifact.read()
        error = "Invalid STALAGMIGHT file: expected a valid SQLite database."
        # SQLite treats an empty file as a new database; require an actual header.
        if not content.startswith(b"SQLite format 3\x00"):
            raise ValidationError(error)

        # Validate a private snapshot before touching the existing project source.
        # Immutable mode prevents journal/sidecar writes during inspection.
        with TemporaryDirectory(prefix="stalagmight-validation-") as directory:
            source = Path(directory) / "source.stalx"
            source.write_bytes(content)
            try:
                with closing(
                    sqlite3.connect(source.as_uri() + "?mode=ro&immutable=1", uri=True)
                ) as connection:
                    result = connection.execute("PRAGMA integrity_check(1)").fetchall()
                    if result != [("ok",)]:
                        raise ValidationError(error)
            except sqlite3.DatabaseError as exc:
                raise ValidationError(error) from exc

        target = self.storage_folder / self.TARGET_SAVE_FILENAME
        target.write_bytes(content)
        return [target]
