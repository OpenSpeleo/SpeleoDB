"""Failure-safe replacement of a generated artifact at an existing commit."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

import orjson
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

if TYPE_CHECKING:
    from django.db.models.fields.files import FieldFile

    from speleodb.gis.models import ProjectGeoJSON
    from speleodb.surveys.models import Project
    from speleodb.surveys.models import ProjectCommit

logger = logging.getLogger(__name__)


def _remove_unpublished_file(file: FieldFile) -> None:
    try:
        file.delete(save=False)
    except Exception:
        # Cleanup failure must not roll back a successfully published artifact.
        logger.exception("Unable to remove unpublished GeoJSON %s", file.name)


def replace_project_geojson(
    project: Project,
    commit: ProjectCommit,
    data: dict[str, Any],
    *,
    replace_existing: bool = True,
) -> ProjectGeoJSON:
    """Upload first, atomically replace the row, and retain the previous blob.

    Publication owns a short transaction after storage I/O. Normal model updates
    remain forbidden; a replacement is a new immutable artifact at the same Git SHA.
    Retired objects remain readable by in-flight requests and issued signed URLs.
    """
    replacement = project.geojsons.model(
        project=project,
        commit=commit,
        file=SimpleUploadedFile(
            "replacement.geojson",
            orjson.dumps(data),
            content_type="application/geo+json",
        ),
    )
    # The existing commit primary key is deliberately replaced below. Validate
    # the source before any upload or removal, excluding only that uniqueness.
    replacement.full_clean(validate_unique=False)
    # Choose the immutable key before storage I/O. Failed uploads are removed
    # immediately; a hard-killed upload may leave an orphan for a full reset.
    key = replacement.file.field.generate_filename(replacement, "replacement.geojson")
    replacement.file.name = key
    try:
        stored_name = replacement.file.storage.save(
            key,
            replacement.file.file,
            max_length=replacement.file.field.max_length,
        )
        replacement.file.name = stored_name
        replacement.file._committed = True  # type: ignore[attr-defined]  # noqa: SLF001
        if stored_name != key:
            raise RuntimeError(  # noqa: TRY301 - Cleanup includes unexpected storage paths.
                "GeoJSON storage changed its reserved immutable key."
            )
        with transaction.atomic():
            # Lock the stable parent even when its artifact does not exist yet.
            type(commit).objects.select_for_update().get(pk=commit.pk)
            previous = project.geojsons.filter(pk=commit.pk).first()
            if previous is not None and not replace_existing:
                _remove_unpublished_file(replacement.file)
                return previous
            if previous is not None:
                # QuerySet.delete intentionally skips the model's immediate blob
                # deletion. A rollback must leave the previous download usable.
                project.geojsons.filter(pk=commit.pk).delete()
            replacement.save(force_insert=True)
            if previous is not None:
                transaction.on_commit(
                    lambda: logger.info(
                        "Retained retired GeoJSON object %s after replacement "
                        "by %s; "
                        "clean up only after issued URLs and active readers expire",
                        previous.file.name,
                        replacement.file.name,
                    ),
                    robust=True,
                )
    except Exception:
        _remove_unpublished_file(replacement.file)
        raise
    return replacement
