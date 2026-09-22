"""Generate maps from committed sources without running work in upload requests."""

from __future__ import annotations

import logging
from contextlib import closing
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import sentry_sdk
from botocore.exceptions import BotoCoreError
from botocore.exceptions import ClientError
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from compass_lib.geojson import NoKnownAnchorError as CompassNoKnownAnchorError
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from openspeleo_lib.errors import EmptySurveyError
from openspeleo_lib.geojson import NoKnownAnchorError
from pydantic import ValidationError as PydanticValidationError

from speleodb.background_jobs.archive_sources import ArchiveBuildError
from speleodb.background_jobs.archive_sources import mirror_project
from speleodb.background_jobs.archive_sources import project_git_source
from speleodb.gis.geojson_generation import ERROR_LIMIT
from speleodb.gis.geojson_generation import GeoJSONOwnershipLostError
from speleodb.gis.geojson_generation import assert_geojson_ownership
from speleodb.gis.geojson_generation import claim_geojson_generation
from speleodb.gis.geojson_generation import dispatch_pending_geojsons
from speleodb.gis.geojson_generation import finish_geojson_generation
from speleodb.gis.geojson_generation import mark_geojson_ready
from speleodb.gis.geojson_generation import reserve_geojson_object
from speleodb.gis.geojson_sources import materialize_geojson_source
from speleodb.gis.project_geojson_services import replace_project_geojson
from speleodb.git_engine.core import GitRepo
from speleodb.utils.exceptions import reraise_task_timeout

logger = logging.getLogger(__name__)


def _exception_chain(error: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


def _failure_details(error: Exception, phase: str) -> tuple[str, str, bool, bool]:
    """Return bounded public diagnostics without exposing paths or credentials."""
    chain = _exception_chain(error)
    if any(isinstance(item, SoftTimeLimitExceeded) for item in chain):
        return "worker_timeout", "Map generation exceeded its time limit.", True, False
    if any(
        isinstance(item, (NoKnownAnchorError, CompassNoKnownAnchorError))
        for item in chain
    ):
        return "no_anchor", "No usable GPS anchor was found in the survey.", False, True
    if any(isinstance(item, EmptySurveyError) for item in chain):
        return "empty_survey", "The survey contains no shots.", False, True
    validation = next(
        (item for item in chain if isinstance(item, PydanticValidationError)), None
    )
    if validation is not None:
        # openspeleo-lib attaches station/field context without rendering the
        # potentially enormous Pydantic input payload. Never use str(validation).
        notes = getattr(validation, "__notes__", [])
        details = "\n".join(str(note)[:ERROR_LIMIT] for note in notes[:20])
        message = "The survey contains invalid data."
        if details:
            message += f"\n{details}"
        return "invalid_survey", message[:ERROR_LIMIT], False, False
    if any(isinstance(item, DjangoValidationError) for item in chain):
        return (
            "invalid_geojson",
            "The generated map is not valid GeoJSON.",
            False,
            False,
        )
    if phase in {"clone", "publish"} or any(
        isinstance(
            item,
            (
                ArchiveBuildError,
                DatabaseError,
                BotoCoreError,
                ClientError,
                TimeoutError,
            ),
        )
        for item in chain
    ):
        return (
            "infrastructure_error",
            "Map generation could not access its source or artifact storage.",
            True,
            False,
        )
    return "invalid_survey", "The survey could not be converted to a map.", False, False


def _report_failure(error: Exception, commit_id: str, code: str) -> None:
    logger.error(
        "GeoJSON generation failed for commit %s (%s; %s)",
        commit_id,
        code,
        type(error).__name__,
    )
    try:
        sentry_sdk.capture_exception(error)
    except Exception:
        logger.exception("Unable to report GeoJSON generation failure")


@shared_task(name="speleodb.gis.tasks.dispatch_project_geojsons")
def dispatch_project_geojsons() -> None:
    """Publish only durable rows visible after their upload transaction commits."""
    dispatch_pending_geojsons()


@shared_task(
    name="speleodb.gis.tasks.generate_project_geojson",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=settings.GEOJSON_GENERATION_SOFT_TIME_LIMIT,
    time_limit=settings.GEOJSON_GENERATION_HARD_TIME_LIMIT,
)
def generate_project_geojson(commit_id: str, token: str) -> None:
    generation = claim_geojson_generation(commit_id, token)
    if generation is None:
        return
    project = generation.commit.project
    heartbeat = partial(assert_geojson_ownership, commit_id, token)
    phase = "clone"
    try:
        scratch = Path(settings.GEOJSON_GENERATION_SCRATCH_DIR)
        scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=f"{token}-", dir=scratch) as temporary:
            directory = Path(temporary)
            repository = directory / "repository"
            mirror_project(
                project_git_source(project.pk),
                repository,
                heartbeat=heartbeat,
            )
            heartbeat()
            phase = "materialize"
            sources = directory / "sources"
            sources.mkdir()
            with closing(GitRepo(repository)) as git_repo:
                git_commit = git_repo.commit(commit_id)
                source = materialize_geojson_source(project, git_commit, sources)
            if source is None:
                finish_geojson_generation(
                    commit_id,
                    token,
                    code="missing_source",
                    message="This revision has no complete supported survey source.",
                    skipped=True,
                )
                return
            heartbeat()
            phase = "convert"
            data: dict[str, Any] = project.build_geojson(source)
            heartbeat()
            phase = "publish"
            replace_project_geojson(
                project,
                generation.commit,
                data,
                replace_existing=False,
                before_upload=partial(reserve_geojson_object, commit_id, token),
                before_publish=partial(mark_geojson_ready, commit_id, token),
            )
    except GeoJSONOwnershipLostError:
        logger.info("Discarded expired or superseded GeoJSON result for %s", commit_id)
    except Exception as error:  # noqa: BLE001 - Durable failure is owned by this task.
        code, message, retryable, skipped = _failure_details(error, phase)
        finish_geojson_generation(
            commit_id,
            token,
            code=code,
            message=message,
            retryable=retryable,
            skipped=skipped,
        )
        if not skipped:
            _report_failure(error, commit_id, code)
        # A worker timeout must remain visible to Celery and stop execution.
        reraise_task_timeout(error)
