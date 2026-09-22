"""Failure-safe replacement of a generated artifact at an existing commit."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

import orjson
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from speleodb.gis.geojson_generation import reconcile_published_geojson
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import ProjectCommit

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.db.models.fields.files import FieldFile

    from speleodb.surveys.models import Project

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
    before_upload: Callable[[str], None] | None = None,
    before_publish: Callable[[bool], None] | None = None,
) -> ProjectGeoJSON:
    """Upload first, atomically replace the row, and retain the previous blob.

    Publication owns a short transaction after storage I/O. Normal model updates
    remain forbidden; a replacement is a new immutable artifact at the same Git SHA.
    Retired objects remain readable by in-flight requests and issued signed URLs.
    """
    replacement = ProjectGeoJSON(
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
    # Reserve the immutable key before storage I/O so async jobs can journal an
    # upload even if the worker is killed before the storage call returns.
    key = replacement.file.field.generate_filename(replacement, "replacement.geojson")
    if before_upload is not None:
        before_upload(key)
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
            ProjectCommit.objects.select_for_update().get(pk=commit.pk)
            previous = ProjectGeoJSON.objects.filter(pk=commit.pk).first()
            # Async jobs fence their token/deadline after the upload, and mark
            # their durable state ready in the same transaction as this insert.
            if before_publish is not None:
                before_publish(previous is None or replace_existing)
            else:
                reconcile_published_geojson(commit.pk)
            if previous is not None and not replace_existing:
                _remove_unpublished_file(replacement.file)
                return previous
            if previous is not None:
                # QuerySet.delete intentionally skips the model's immediate blob
                # deletion. A rollback must leave the previous download usable.
                ProjectGeoJSON.objects.filter(pk=commit.pk).delete()
            replacement.save(force_insert=True)
            if previous is not None:
                transaction.on_commit(
                    lambda: logger.info(
                        "Retained retired GeoJSON object %s after replacement by %s; "
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
