"""Persist and fence GeoJSON work; only the dispatcher contacts the broker."""

from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from celery import current_app
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from speleodb.common.enums import ProjectType
from speleodb.gis.models import ProjectGeoJSON
from speleodb.gis.models.project_geojson_generation import GeoJSONGenerationState
from speleodb.gis.models.project_geojson_generation import ProjectGeoJSONGeneration
from speleodb.utils.exceptions import reraise_task_timeout

if TYPE_CHECKING:
    from speleodb.surveys.models import Project
    from speleodb.surveys.models import ProjectCommit

logger = logging.getLogger(__name__)
GENERATION_TASK = "speleodb.gis.tasks.generate_project_geojson"
ACTIVE_STATES = (
    GeoJSONGenerationState.PENDING,
    GeoJSONGenerationState.QUEUED,
    GeoJSONGenerationState.RUNNING,
)
ERROR_LIMIT = 2000


class GeoJSONOwnershipLostError(Exception):
    """This execution was superseded, expired, or its source was deleted."""


def _retry_delay(attempts: int) -> timedelta:
    seconds = settings.GEOJSON_GENERATION_RETRY_BASE_SECONDS
    maximum = settings.GEOJSON_GENERATION_RETRY_MAX_SECONDS
    for _ in range(max(0, attempts - 1)):
        if seconds >= maximum:
            break
        seconds *= 2
    return timedelta(seconds=min(seconds, maximum))


def request_geojson_generation(
    project: Project, commit: ProjectCommit
) -> ProjectGeoJSONGeneration:
    """Record work after a successful source push; never publish to Celery here.

    The caller owns the upload transaction. A dispatcher on another connection
    cannot observe this row until that transaction commits. Failed bookkeeping
    can be repaired by adding this commit in the generation admin.
    """
    if commit.project_id != project.pk:
        raise ValueError("The source commit belongs to another project.")
    now = timezone.now()
    skipped = project.exclude_geojson or project.type not in {
        ProjectType.ARIANE,
        ProjectType.COMPASS,
    }
    generation, _ = ProjectGeoJSONGeneration.objects.get_or_create(
        commit=commit,
        defaults={
            "state": (
                GeoJSONGenerationState.SKIPPED
                if skipped
                else GeoJSONGenerationState.PENDING
            ),
            "next_attempt_at": None if skipped else now,
            "created_at": now,
            "updated_at": now,
            "last_error_code": "excluded" if skipped else "",
            "last_error": "GeoJSON generation is disabled." if skipped else "",
        },
    )
    return generation


def retry_geojson_generation(commit: ProjectCommit) -> ProjectGeoJSONGeneration:
    """Recover missing bookkeeping or retry terminal work without reuploading."""
    with transaction.atomic():
        generation = request_geojson_generation(commit.project, commit)
        generation = ProjectGeoJSONGeneration.objects.select_for_update().get(
            pk=generation.pk
        )
        if generation.state in ACTIVE_STATES:
            return generation
        if generation.unpublished_objects:
            raise ValueError(
                "Artifact cleanup is pending. Retry after cleanup finishes."
            )
        if commit.project.exclude_geojson:
            raise ValueError("This project is excluded from GeoJSON generation.")
        if commit.project.type not in {ProjectType.ARIANE, ProjectType.COMPASS}:
            raise ValueError("This project type has no GeoJSON exporter.")
        now = timezone.now()
        generation.state = GeoJSONGenerationState.PENDING
        generation.attempts = 0
        generation.dispatch_attempts = 0
        generation.next_attempt_at = now
        generation.token = uuid.uuid4()
        generation.lease_expires_at = None
        generation.last_error_code = ""
        generation.last_error = ""
        generation.updated_at = now
        generation.save()
        return generation


def _finish(
    generation: ProjectGeoJSONGeneration,
    state: str,
    *,
    now: datetime,
    code: str = "",
    message: str = "",
) -> None:
    generation.state = state
    generation.next_attempt_at = None
    generation.lease_expires_at = None
    generation.last_error_code = code
    generation.last_error = message[:ERROR_LIMIT]
    generation.updated_at = now
    generation.save()


def _fail(
    generation: ProjectGeoJSONGeneration,
    *,
    now: datetime,
    code: str,
    message: str,
    retryable: bool,
) -> None:
    retry = retryable and generation.attempts < settings.GEOJSON_GENERATION_MAX_ATTEMPTS
    _finish(
        generation,
        GeoJSONGenerationState.PENDING if retry else GeoJSONGenerationState.FAILED,
        now=now,
        code=code,
        message=message,
    )
    if retry:
        generation.next_attempt_at = now + _retry_delay(generation.attempts)
        generation.token = uuid.uuid4()
        generation.save(update_fields=["next_attempt_at", "token"])


def _reserve_dispatch(commit_id: str) -> tuple[str, uuid.UUID] | None:
    now = timezone.now()
    with transaction.atomic():
        generation = (
            ProjectGeoJSONGeneration.objects.select_for_update(skip_locked=True)
            .filter(pk=commit_id)
            .first()
        )
        if generation is None or generation.state not in ACTIVE_STATES:
            return None
        if generation.state == GeoJSONGenerationState.RUNNING:
            if generation.lease_expires_at is None or generation.lease_expires_at > now:
                return None
            _fail(
                generation,
                now=now,
                code="worker_timeout",
                message="The map worker did not finish before its deadline.",
                retryable=True,
            )
            return None
        if generation.state == GeoJSONGenerationState.QUEUED:
            if generation.lease_expires_at is None or generation.lease_expires_at > now:
                return None
        elif generation.next_attempt_at is None or generation.next_attempt_at > now:
            return None
        generation.state = GeoJSONGenerationState.QUEUED
        generation.token = uuid.uuid4()
        generation.dispatch_attempts += 1
        generation.next_attempt_at = None
        generation.lease_expires_at = now + timedelta(
            seconds=settings.GEOJSON_GENERATION_DISPATCH_LEASE_SECONDS
        )
        generation.updated_at = now
        generation.save()
        return generation.commit_id, generation.token


def cleanup_geojson_work() -> None:
    """Reclaim abandoned, journaled objects without deleting published artifacts."""
    now = timezone.now()
    commits = (
        ProjectGeoJSONGeneration.objects.exclude(unpublished_objects=[])
        .order_by("updated_at", "commit_id")
        .values_list("commit_id", flat=True)[
            : settings.GEOJSON_GENERATION_DISPATCH_BATCH
        ]
    )
    storage = ProjectGeoJSON._meta.get_field("file").storage  # noqa: SLF001
    for commit_id in commits:
        with transaction.atomic():
            generation = (
                ProjectGeoJSONGeneration.objects.select_for_update(skip_locked=True)
                .filter(pk=commit_id)
                .first()
            )
            if generation is None:
                continue
            retained = []
            for entry in generation.unpublished_objects:
                if datetime.fromisoformat(entry["cleanup_after"]) > now or (
                    str(generation.token) == entry["token"]
                    and generation.state == GeoJSONGenerationState.RUNNING
                    and generation.lease_expires_at is not None
                    and generation.lease_expires_at > now
                ):
                    retained.append(entry)
                    continue
                if not ProjectGeoJSON.objects.filter(file=entry["key"]).exists():
                    try:
                        storage.delete(entry["key"])
                    except Exception as error:  # noqa: BLE001 - Retain cleanup work.
                        reraise_task_timeout(error)
                        logger.warning(
                            "Unable to clean unpublished GeoJSON %s", entry["key"]
                        )
                        retained.append(entry)
            # Rotate every inspected journal, including failed deletions and
            # objects still in their grace period. Otherwise a full oldest
            # batch can permanently starve cleanup for later generations.
            generation.unpublished_objects = retained
            generation.updated_at = now
            generation.save(update_fields=["unpublished_objects", "updated_at"])
    root = Path(settings.GEOJSON_GENERATION_SCRATCH_DIR)
    if not root.is_dir():
        return
    cutoff = now.timestamp() - (
        settings.GEOJSON_GENERATION_HARD_TIME_LIMIT
        + settings.GEOJSON_GENERATION_CLEANUP_GRACE_SECONDS
    )
    for directory in root.iterdir():
        try:
            if directory.is_symlink() or not directory.is_dir():
                continue
            token = uuid.UUID(directory.name[:36])
            if (
                not directory.name.startswith(f"{token}-")
                or directory.stat().st_mtime > cutoff
            ):
                continue
            if not ProjectGeoJSONGeneration.objects.filter(
                token=token,
                state=GeoJSONGenerationState.RUNNING,
                lease_expires_at__gt=now,
            ).exists():
                shutil.rmtree(directory)
        except ValueError:
            continue
        except OSError:
            logger.warning("Unable to clean abandoned GeoJSON workspace %s", directory)


def dispatch_pending_geojsons() -> None:
    """Recover leases and publish a bounded batch of committed work records."""
    cleanup_geojson_work()
    now = timezone.now()
    candidates = (
        ProjectGeoJSONGeneration.objects.filter(
            Q(state=GeoJSONGenerationState.PENDING, next_attempt_at__lte=now)
            | Q(
                state__in=[
                    GeoJSONGenerationState.QUEUED,
                    GeoJSONGenerationState.RUNNING,
                ],
                lease_expires_at__lte=now,
            )
        )
        .order_by("updated_at", "commit_id")
        .values_list("commit_id", flat=True)[
            : settings.GEOJSON_GENERATION_DISPATCH_BATCH
        ]
    )
    for commit_id in candidates:
        reservation = _reserve_dispatch(commit_id)
        if reservation is None:
            continue
        _, token = reservation
        try:
            current_app.send_task(
                GENERATION_TASK,
                args=[commit_id, str(token)],
                task_id=str(token),
                queue="background_control",
                retry=False,
            )
        except Exception as error:  # noqa: BLE001 - Persist ambiguous broker delivery.
            reraise_task_timeout(error)
            # Delivery can be ambiguous. A worker which already claimed this
            # token wins; never move that running execution back to pending.
            with transaction.atomic():
                generation = (
                    ProjectGeoJSONGeneration.objects.select_for_update()
                    .filter(
                        pk=commit_id, token=token, state=GeoJSONGenerationState.QUEUED
                    )
                    .first()
                )
                if generation is not None:
                    now = timezone.now()
                    generation.state = GeoJSONGenerationState.PENDING
                    generation.next_attempt_at = now + _retry_delay(
                        generation.dispatch_attempts
                    )
                    generation.lease_expires_at = None
                    generation.last_error_code = "broker_unavailable"
                    generation.last_error = (
                        "Map generation is waiting for the background queue."
                    )
                    generation.updated_at = now
                    generation.save()
            logger.warning("GeoJSON dispatch deferred for commit %s", commit_id)


def claim_geojson_generation(
    commit_id: str, token: str
) -> ProjectGeoJSONGeneration | None:
    now = timezone.now()
    with transaction.atomic():
        generation = (
            ProjectGeoJSONGeneration.objects.select_for_update(of=("self",))
            .select_related("commit__project")
            .filter(
                pk=commit_id,
                token=token,
                state=GeoJSONGenerationState.QUEUED,
                lease_expires_at__gt=now,
            )
            .first()
        )
        if generation is None:
            return None
        # The query's timestamp predates any wait for its row lock. Recheck
        # after acquisition before starting an execution on an expired lease.
        now = timezone.now()
        if generation.lease_expires_at is None or generation.lease_expires_at <= now:
            return None
        project = generation.commit.project
        if project.exclude_geojson or project.type not in {
            ProjectType.ARIANE,
            ProjectType.COMPASS,
        }:
            _finish(
                generation,
                GeoJSONGenerationState.SKIPPED,
                now=now,
                code="excluded",
                message="GeoJSON generation is disabled.",
            )
            return None
        if ProjectGeoJSON.objects.filter(commit_id=commit_id).exists():
            _finish(generation, GeoJSONGenerationState.READY, now=now)
            return None
        generation.state = GeoJSONGenerationState.RUNNING
        generation.attempts += 1
        generation.lease_expires_at = now + timedelta(
            seconds=settings.GEOJSON_GENERATION_HARD_TIME_LIMIT
        )
        generation.last_error_code = ""
        generation.last_error = ""
        generation.updated_at = now
        generation.save()
        return generation


def assert_geojson_ownership(commit_id: str, token: str) -> None:
    if not ProjectGeoJSONGeneration.objects.filter(
        pk=commit_id,
        token=token,
        state=GeoJSONGenerationState.RUNNING,
        lease_expires_at__gt=timezone.now(),
    ).exists():
        raise GeoJSONOwnershipLostError


def reserve_geojson_object(commit_id: str, token: str, key: str) -> None:
    """Durably record the storage key before any external upload can start."""
    with transaction.atomic():
        generation = (
            ProjectGeoJSONGeneration.objects.select_for_update()
            .filter(
                pk=commit_id,
                token=token,
                state=GeoJSONGenerationState.RUNNING,
                lease_expires_at__gt=timezone.now(),
            )
            .first()
        )
        now = timezone.now()
        if (
            generation is None
            or generation.lease_expires_at is None
            or generation.lease_expires_at <= now
        ):
            raise GeoJSONOwnershipLostError
        if (
            len(generation.unpublished_objects)
            >= settings.GEOJSON_GENERATION_MAX_ATTEMPTS
        ):
            raise RuntimeError("Previous artifact uploads are still awaiting cleanup.")
        cleanup_after = generation.lease_expires_at + timedelta(
            seconds=settings.GEOJSON_GENERATION_CLEANUP_GRACE_SECONDS
        )
        generation.unpublished_objects.append(
            {"key": key, "token": token, "cleanup_after": cleanup_after.isoformat()}
        )
        generation.save(update_fields=["unpublished_objects"])


def mark_geojson_ready(
    commit_id: str, token: str, publish_replacement: bool = True
) -> None:
    """Fence publication inside the artifact service's SQL transaction."""
    generation = (
        ProjectGeoJSONGeneration.objects.select_for_update()
        .filter(
            pk=commit_id,
            token=token,
            state=GeoJSONGenerationState.RUNNING,
            lease_expires_at__gt=timezone.now(),
        )
        .first()
    )
    now = timezone.now()
    if (
        generation is None
        or generation.lease_expires_at is None
        or generation.lease_expires_at <= now
    ):
        raise GeoJSONOwnershipLostError
    if publish_replacement:
        generation.unpublished_objects = [
            entry for entry in generation.unpublished_objects if entry["token"] != token
        ]
    _finish(generation, GeoJSONGenerationState.READY, now=now)


def reconcile_published_geojson(commit_id: str) -> None:
    """Reconcile maintenance publication inside the artifact's SQL transaction.

    A historical rebuild can repair failed work or beat an active upload worker.
    Preserve that worker's upload journal, but revoke its publication ownership.
    """
    generation = (
        ProjectGeoJSONGeneration.objects.select_for_update()
        .filter(pk=commit_id)
        .first()
    )
    if generation is not None:
        _finish(generation, GeoJSONGenerationState.READY, now=timezone.now())


def finish_geojson_generation(
    commit_id: str,
    token: str,
    *,
    code: str,
    message: str,
    retryable: bool = False,
    skipped: bool = False,
) -> None:
    with transaction.atomic():
        generation = (
            ProjectGeoJSONGeneration.objects.select_for_update()
            .filter(pk=commit_id, token=token, state=GeoJSONGenerationState.RUNNING)
            .first()
        )
        if generation is None:
            return
        now = timezone.now()
        if skipped:
            _finish(
                generation,
                GeoJSONGenerationState.SKIPPED,
                now=now,
                code=code,
                message=message,
            )
        else:
            _fail(
                generation,
                now=now,
                code=code,
                message=message,
                retryable=retryable,
            )
