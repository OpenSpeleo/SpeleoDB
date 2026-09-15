"""Retention must not delete an accepted retry or lose outstanding object cleanup."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from queue import Queue
from typing import TYPE_CHECKING
from typing import Any

import pytest
from django.db import connection
from django.db import connections
from django.db.models.signals import pre_delete
from django.utils import timezone

from speleodb.background_jobs.models import BackgroundJob
from speleodb.background_jobs.models import JobAttempt
from speleodb.background_jobs.models import JobState
from speleodb.background_jobs.services import ExportUnavailableError
from speleodb.background_jobs.services import request_notification
from speleodb.background_jobs.services import retry_export
from speleodb.background_jobs.tasks import delete_expired_artifacts
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from collections.abc import Callable
    from concurrent.futures import Future

    from speleodb.users.models import User

pytestmark = pytest.mark.django_db


def _old_failed_job(user: User) -> BackgroundJob:
    job = BackgroundJob.objects.create(requester=user, state=JobState.FAILED)
    JobAttempt.objects.create(job=job, number=1, state=JobState.FAILED)
    BackgroundJob.objects.filter(pk=job.pk).update(
        updated_at=timezone.now() - timedelta(days=91)
    )
    return job


def test_history_retention_preserves_recent_active_and_unremoved_objects() -> None:
    old = _old_failed_job(UserFactory.create())
    recent = _old_failed_job(UserFactory.create())
    active = _old_failed_job(UserFactory.create())
    pending = _old_failed_job(UserFactory.create())
    BackgroundJob.objects.filter(pk=recent.pk).update(updated_at=timezone.now())
    BackgroundJob.objects.filter(pk=active.pk).update(state=JobState.QUEUED)
    JobAttempt.objects.filter(job=pending).update(
        object_key=f"exports/{pending.requester_id}/{pending.pk}/pending.zip"
    )

    delete_expired_artifacts.run()

    assert not BackgroundJob.objects.filter(pk=old.pk).exists()
    assert set(BackgroundJob.objects.values_list("pk", flat=True)) == {
        recent.pk,
        active.pk,
        pending.pk,
    }


def test_retention_rechecks_a_retry_accepted_after_candidate_selection() -> None:
    user = UserFactory.create()
    job = _old_failed_job(user)
    accepted: BackgroundJob | None = None

    def retry_after_selection(
        execute: Callable[..., Any],
        sql: str,
        params: Any,
        many: bool,
        context: dict[str, Any],
    ) -> Any:
        nonlocal accepted
        result = execute(sql, params, many, context)
        if (
            accepted is None
            and sql.startswith("SELECT")
            and 'FROM "background_jobs_backgroundjob"' in sql
            and '"updated_at" <' in sql
            and "FOR UPDATE" not in sql
        ):
            # Let the real SELECT capture an old candidate, then perform the
            # real transition before cleanup starts collecting its children.
            accepted = job
            accepted = retry_export(job, user)
        return result

    with connection.execute_wrapper(retry_after_selection):
        delete_expired_artifacts.run()

    assert accepted is not None
    job.refresh_from_db()
    assert job.state == JobState.QUEUED
    assert job.current_attempt_id == accepted.current_attempt_id
    assert job.attempts.count() == 2  # noqa: PLR2004


@pytest.mark.parametrize("action", [retry_export, request_notification])
def test_pruned_jobs_return_a_controlled_unavailable_error(
    action: Callable[[BackgroundJob, User], object],
) -> None:
    user = UserFactory.create()
    job = _old_failed_job(user)
    BackgroundJob.objects.filter(pk=job.pk).delete()
    with pytest.raises(ExportUnavailableError, match="no longer available"):
        action(job, user)


@pytest.mark.django_db(transaction=True)
def test_retention_holds_the_job_lock_until_cascade_deletion_finishes() -> None:
    if connection.vendor != "postgresql":
        pytest.skip(
            "Concurrent retention requires the PostgreSQL integration database."
        )
    user = UserFactory.create()
    job = _old_failed_job(user)
    backend_pids: Queue[int] = Queue()
    retried: Future[BackgroundJob] | None = None

    def retry_from_another_connection() -> BackgroundJob:
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_pids.put(cursor.fetchone()[0])
            return retry_export(job, user)
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=1) as executor:

        def inspect_deletion_lock(
            sender: type[BackgroundJob], instance: BackgroundJob, **kwargs: Any
        ) -> None:
            nonlocal retried
            if instance.pk != job.pk:
                return
            retried = executor.submit(retry_from_another_connection)
            retry_pid = backend_pids.get(timeout=5)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_backend_pid() = ANY(pg_blocking_pids(%s))",
                        [retry_pid],
                    )
                    if cursor.fetchone()[0]:
                        return
                if retried.done():
                    pytest.fail(
                        "Cleanup did not lock the job before collecting children."
                    )
                time.sleep(0.01)
            pytest.fail(
                "The concurrent retry did not wait for the cleanup transaction."
            )

        pre_delete.connect(inspect_deletion_lock, sender=BackgroundJob, weak=False)
        try:
            delete_expired_artifacts.run()
        finally:
            pre_delete.disconnect(inspect_deletion_lock, sender=BackgroundJob)
        assert retried is not None
        with pytest.raises(ExportUnavailableError, match="no longer available"):
            retried.result(timeout=5)
    assert not BackgroundJob.objects.filter(pk=job.pk).exists()
