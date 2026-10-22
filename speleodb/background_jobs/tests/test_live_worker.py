"""PostgreSQL/Redis/RustFS tests with an actual Celery subprocess."""

from __future__ import annotations

import io
import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from http import HTTPStatus
from textwrap import dedent
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import urlsplit
from zipfile import ZipFile

import orjson
import psycopg
import pytest
import requests
from botocore.exceptions import ClientError
from celery import Celery
from celery._state import get_current_app
from django.conf import settings
from django.db import connection
from django.utils import timezone
from django_celery_results.models import TaskResult
from rest_framework.test import APIClient

from speleodb.background_jobs.models import BackgroundJob
from speleodb.background_jobs.models import JobArtifact
from speleodb.background_jobs.models import JobAttempt
from speleodb.background_jobs.models import JobState
from speleodb.background_jobs.services import GENERATION_TASK
from speleodb.background_jobs.services import request_export
from speleodb.background_jobs.storage import delete_archive
from speleodb.testing.celery import isolated_test_broker_url
from speleodb.testing.database import postgres_test_database_url
from speleodb.users.models import User
from speleodb.users.tasks import get_users_count
from speleodb.users.tests.factories import VerifiedUserFactory
from speleodb.utils.s3_storages import ExportStorage

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator
    from collections.abc import Mapping
    from pathlib import Path

    from django.http import HttpResponse

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.live_services,
]

WAIT_SECONDS: int = 45
TEST_BUCKET: str = "speleodb-user-artifacts-test"
MAINTENANCE_TASK: str = "speleodb.background_jobs.tasks.maintain_background_jobs"
CLEANUP_TASK: str = "speleodb.background_jobs.tasks.delete_expired_artifacts"


@contextmanager
def _publisher(broker_url: str) -> Iterator[Celery]:
    """Use a fresh real connection pool when switching between live/dead brokers."""
    previous: Celery = get_current_app()
    with Celery(f"exports-test-{uuid.uuid4()}") as application:
        application.config_from_object("django.conf:settings", namespace="CELERY")
        application.conf.update(
            broker_url=broker_url,
            broker_read_url=broker_url,
            broker_write_url=broker_url,
            broker_connection_timeout=1,
            broker_transport_options={
                "socket_connect_timeout": 1,
                "socket_timeout": 2,
                "visibility_timeout": 3600,
            },
            task_always_eager=False,
        )
        application.autodiscover_tasks(force=True)
        try:
            yield application
        finally:
            previous.set_current()


@dataclass
class LiveWorker:
    application: Celery
    process: subprocess.Popen[bytes]
    log_path: Path
    hostname: str
    environment: dict[str, str]

    def restart(self) -> None:
        assert self.process.poll() is not None
        with self.log_path.open("ab") as log:
            self.process = subprocess.Popen(  # noqa: S603 - Reuse this fixture's worker.
                self.process.args,
                env=self.environment,
                cwd=settings.BASE_DIR,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        self.wait_for(
            lambda: bool(
                self.application.control.inspect(
                    destination=[self.hostname], timeout=1
                ).ping()
            )
        )

    def wait_for(self, predicate: Callable[[], bool]) -> None:
        deadline: float = time.monotonic() + WAIT_SECONDS
        while time.monotonic() < deadline:
            assert self.process.poll() is None, (
                f"Celery exited unexpectedly; inspect {self.log_path}."
            )
            if predicate():
                return
            time.sleep(0.2)
        pytest.fail(f"Timed out waiting for the live worker; inspect {self.log_path}.")

    def wait_ready(self, job: BackgroundJob) -> JobAttempt:
        self.wait_for(
            lambda: BackgroundJob.objects.filter(
                pk=job.pk, state=JobState.READY
            ).exists()
        )
        job.refresh_from_db()
        assert job.current_attempt_id is not None
        attempt: JobAttempt = job.attempts.get(pk=job.current_attempt_id)
        self.wait_for(
            lambda: TaskResult.objects.filter(
                task_id=str(attempt.task_id), status="SUCCESS"
            ).exists()
        )
        return attempt

    def wait_task_success(self, name: str, task_id: str) -> None:
        # Celery logs success after task execution and backend handling finish.
        # Housekeeping intentionally has no successful result row to poll.
        self.wait_for(
            lambda: (
                f"Task {name}[{task_id}] succeeded"
                in self.log_path.read_text(encoding="utf-8")
            )
        )

    def run_control_task(self, name: str) -> str:
        task_id: str = str(uuid.uuid4())
        self.application.tasks[name].apply_async(
            queue="background_control", task_id=task_id
        )
        self.wait_task_success(name, task_id)
        return task_id


@pytest.fixture
def live_worker(
    tmp_path: Path, transactional_db: None, request: pytest.FixtureRequest
) -> Iterator[LiveWorker]:
    broker_url: str = isolated_test_broker_url()
    assert settings.AWS_STORAGE_BUCKET_NAME == TEST_BUCKET
    assert urlsplit(settings.AWS_S3_ENDPOINT_URL).hostname in {
        "localhost",
        "127.0.0.1",
        "rustfs",
    }, "Use the local RustFS test bucket."
    database_url: str = postgres_test_database_url()
    ExportStorage().connection.meta.client.head_bucket(Bucket=TEST_BUCKET)
    hostname: str = f"exports-integration-{uuid.uuid4()}@localhost"
    environment: dict[str, str] = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.test_celery",
            "TEST_DATABASE_URL": database_url,
            "TEST_CELERY_BROKER_URL": broker_url,
            "CELERY_BROKER_URL": broker_url,
            "EXPORTS_SCRATCH_DIR": str(tmp_path / "scratch"),
            "PYTHONUNBUFFERED": "1",
            "SPELEODB_CELERY_WORKER_RUNTIME": "true",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "POLARS_MAX_THREADS": "1",
        }
    )
    if getattr(request, "param", None) == "hard-timeout":
        environment["DJANGO_SETTINGS_MODULE"] = (
            "config.settings.test_celery_hard_timeout"
        )
    arguments: list[str] = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "config.celery_app",
        "--skip-checks",
        "worker",
        "--pool",
        "prefork",
        "--concurrency",
        "1",
        "--prefetch-multiplier",
        "1",
        "--queues",
        "exports,background_control",
        "--hostname",
        hostname,
        "--loglevel",
        "INFO",
        "--without-gossip",
        "--without-mingle",
    ]
    log_path: Path = tmp_path / "celery-worker.log"
    with _publisher(broker_url) as application, log_path.open("wb") as log:
        with application.connection_for_write() as broker_connection:
            broker_connection.ensure_connection(max_retries=0)
        process: subprocess.Popen[bytes] = subprocess.Popen(  # noqa: S603
            arguments,
            env=environment,
            cwd=settings.BASE_DIR,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        worker: LiveWorker = LiveWorker(
            application, process, log_path, hostname, environment
        )
        try:
            worker.wait_for(
                lambda: bool(
                    application.control.inspect(
                        destination=[hostname], timeout=1
                    ).ping()
                )
            )
            yield worker
        finally:
            worker.process.terminate()
            try:
                worker.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(worker.process.pid, signal.SIGKILL)
                worker.process.wait(timeout=5)
            # Only delete object keys created in this transaction-isolated test DB.
            for attempt in JobAttempt.objects.exclude(object_key="").iterator():
                delete_archive(key=attempt.object_key)


def _publish_scheduled_task(
    live_worker: LiveWorker, task_name: str, task_id: str
) -> None:
    environment: dict[str, str] = live_worker.environment.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.beat",
            "DATABASE_URL": postgres_test_database_url(),
            "USE_DOCKER": "false",
        }
    )
    script: str = dedent(
        """
        import sys
        from importlib import import_module

        from django.db import connection
        from config.celery_app import app
        from speleodb.background_jobs.lease import SchedulerLease

        app.loader.init_worker()
        models = import_module("django_celery_beat.models")
        schedules = import_module("django_celery_beat.schedulers")
        scheduler_module = import_module("speleodb.background_jobs.scheduler")

        assert app.conf.result_backend is None
        assert not any(name.startswith("speleodb.") for name in app.tasks)
        task_name, task_id = sys.argv[1:]
        interval, _ = models.IntervalSchedule.objects.get_or_create(
            every=86400, period="seconds",
        )
        model = models.PeriodicTask.objects.create(
            name=f"live-{task_id}", task=task_name, interval=interval,
            queue="background_control",
        )
        entry = schedules.ModelEntry(model, app=app)
        entry.options["task_id"] = task_id
        lease = SchedulerLease(connection.get_connection_params())
        lease.acquire()
        scheduler = scheduler_module.ExponentialBackoffDatabaseScheduler(
            app=app, lease=lease, lazy=True,
        )
        try:
            scheduler.apply_async(entry, advance=False)
        finally:
            scheduler.close()
            lease.close()
        """
    )
    subprocess.run(  # noqa: S603
        [sys.executable, "-c", script, task_name, task_id],
        env=environment,
        cwd=settings.BASE_DIR,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )


def test_live_worker_consumes_existing_tasks_without_an_explicit_queue(
    live_worker: LiveWorker,
) -> None:
    VerifiedUserFactory.create()
    expected_count: int = get_users_count()
    task_id: str = str(uuid.uuid4())
    task_name: str = "speleodb.users.tasks.get_users_count"
    with psycopg.connect(**connection.get_connection_params()) as blocked_users:
        blocked_users.execute(
            psycopg.sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(
                psycopg.sql.Identifier(User._meta.db_table)  # noqa: SLF001
            )
        )
        live_worker.application.send_task(task_name, task_id=task_id)
        live_worker.wait_for(
            lambda: TaskResult.objects.filter(
                task_id=task_id, status="STARTED"
            ).exists()
        )
        started: Mapping[str, object] = TaskResult.objects.values(
            "id", "date_started"
        ).get(task_id=task_id)
    live_worker.wait_for(
        lambda: TaskResult.objects.filter(task_id=task_id, status="SUCCESS").exists()
    )
    completed: TaskResult = TaskResult.objects.get(task_id=task_id)
    metadata: Mapping[str, object] = TaskResult.objects.values(
        "date_started", "worker"
    ).get(task_id=task_id)
    assert orjson.loads(completed.result or "null") == expected_count
    assert completed.pk == started["id"]
    assert metadata["date_started"] == started["date_started"]
    assert metadata["date_started"] is not None
    assert completed.task_name == task_name
    assert metadata["worker"] == live_worker.hostname
    assert TaskResult.objects.filter(task_id=task_id).count() == 1


@pytest.mark.parametrize(
    "task_name",
    [
        MAINTENANCE_TASK,
        CLEANUP_TASK,
        "celery.backend_cleanup",
    ],
)
def test_live_housekeeping_records_only_failures(
    live_worker: LiveWorker, task_name: str
) -> None:
    direct_id: str = live_worker.run_control_task(task_name)
    assert not TaskResult.objects.filter(task_id=direct_id).exists()

    scheduled_id: str = str(uuid.uuid4())
    _publish_scheduled_task(live_worker, task_name, scheduled_id)
    live_worker.wait_task_success(task_name, scheduled_id)
    assert not TaskResult.objects.filter(task_id=scheduled_id).exists()

    failed_id: str = str(uuid.uuid4())
    # Publish a malformed invocation through the broker, bypassing the local
    # argument check so the actual worker records its unhandled TypeError.
    live_worker.application.send_task(
        task_name,
        kwargs={"unsupported_argument": True},
        task_id=failed_id,
        ignore_result=live_worker.application.tasks[task_name].ignore_result,
    )
    live_worker.wait_for(
        lambda: TaskResult.objects.filter(task_id=failed_id, status="FAILURE").exists()
    )
    failed: TaskResult = TaskResult.objects.get(task_id=failed_id)
    metadata: Mapping[str, object] = TaskResult.objects.values(
        "date_started", "worker"
    ).get(task_id=failed_id)
    assert orjson.loads(failed.result or "null")["exc_type"] == "TypeError"
    assert failed.task_name == task_name
    assert metadata["worker"] == live_worker.hostname
    assert metadata["date_started"] is None
    assert "unsupported_argument" in (failed.traceback or "")


def test_live_prefork_soft_timeout_records_failure_and_accepts_the_next_task(
    live_worker: LiveWorker,
) -> None:
    task_id: str = str(uuid.uuid4())
    with psycopg.connect(**connection.get_connection_params()) as blocked_users:
        blocked_users.execute(
            psycopg.sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(
                psycopg.sql.Identifier(User._meta.db_table)  # noqa: SLF001
            )
        )
        live_worker.application.send_task(
            "speleodb.users.tasks.get_users_count",
            task_id=task_id,
            time_limit=2,
            soft_time_limit=1,
        )
        live_worker.wait_for(
            lambda: TaskResult.objects.filter(
                task_id=task_id, status="FAILURE"
            ).exists()
        )
    failed: TaskResult = TaskResult.objects.get(task_id=task_id)
    # A soft signal during libpq I/O can surface as a driver OperationalError;
    # verify the actual timeout signal as well as the persisted task failure.
    assert "Soft time limit (1s) exceeded" in live_worker.log_path.read_text()
    assert orjson.loads(failed.result or "null")["exc_type"] in {
        "SoftTimeLimitExceeded",
        "OperationalError",
    }
    live_worker.run_control_task("speleodb.users.tasks.get_users_count")


@pytest.mark.parametrize("live_worker", ["hard-timeout"], indirect=True)
def test_live_prefork_hard_timeout_replaces_child_and_accepts_next_task(
    live_worker: LiveWorker,
) -> None:
    task_name: str = "speleodb.users.tasks.get_users_count"
    task_id: str = str(uuid.uuid4())
    with psycopg.connect(**connection.get_connection_params()) as blocked_users:
        blocked_users.execute(
            psycopg.sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(
                psycopg.sql.Identifier(User._meta.db_table)  # noqa: SLF001
            )
        )
        live_worker.application.send_task(
            task_name, task_id=task_id, time_limit=2, soft_time_limit=0
        )
        live_worker.wait_for(
            lambda: TaskResult.objects.filter(
                task_id=task_id, status="FAILURE"
            ).exists()
        )
    failed: TaskResult = TaskResult.objects.get(task_id=task_id)
    assert "TimeLimitExceeded" in (failed.result or "")
    assert "Hard time limit (2s) exceeded" in live_worker.log_path.read_text(
        encoding="utf-8"
    )
    live_worker.run_control_task(task_name)


def test_live_beat_publication_preserves_worker_result_recording(
    live_worker: LiveWorker,
) -> None:
    task_id: str = str(uuid.uuid4())
    _publish_scheduled_task(
        live_worker, "speleodb.users.tasks.get_users_count", task_id
    )
    live_worker.wait_for(
        lambda: TaskResult.objects.filter(task_id=task_id, status="SUCCESS").exists()
    )
    result: TaskResult = TaskResult.objects.get(task_id=task_id)
    metadata: Mapping[str, object] = TaskResult.objects.values(
        "periodic_task_name", "worker"
    ).get(task_id=task_id)
    assert orjson.loads(result.result or "null") == get_users_count()
    assert metadata["periodic_task_name"] == f"live-{task_id}"
    assert metadata["worker"] == live_worker.hostname


def test_live_export_download_notification_and_expiration(
    live_worker: LiveWorker,
) -> None:
    user: User = VerifiedUserFactory.create()
    job: BackgroundJob
    created: bool
    job, created = request_export(user)
    assert created
    live_worker.wait_ready(job)
    artifact: JobArtifact = JobArtifact.objects.get(job=job)
    assert artifact.expires_at - artifact.ready_at == timedelta(hours=24)
    prefix: str = "speleodb-export-"
    suffix: str = f"-{artifact.attempt_id}.zip"
    assert artifact.filename.startswith(prefix)
    assert artifact.filename.endswith(suffix)
    assert artifact.object_key == f"exports/{artifact.filename}"
    generated_at: datetime = datetime.strptime(
        artifact.filename.removeprefix(prefix).removesuffix(suffix),
        "%Y-%m-%dT%H-%M-%SZ",
    ).replace(tzinfo=UTC)
    assert job.created_at.replace(microsecond=0) <= generated_at <= artifact.ready_at

    api: APIClient = APIClient()
    api.force_authenticate(user)
    path: str = f"/api/v2/user/exports/{job.id}/download/"
    response: HttpResponse = api.get(path)
    assert response.status_code == HTTPStatus.FOUND
    download: requests.Response = requests.get(response["Location"], timeout=15)
    download.raise_for_status()
    assert len(download.content) == artifact.size_bytes
    assert download.headers["Content-Disposition"] == (
        f'attachment; filename="{artifact.filename}"'
    )
    assert download.headers["Cache-Control"] == "public, max-age=86400"
    with ZipFile(io.BytesIO(download.content)) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {
            "README.md",
            "manifest.json",
            "projects/",
            "geojsons/",
            "geometries/",
            "layers/",
            "gps tracks/",
            "landmarks/",
        }
        manifest: dict[str, Any] = orjson.loads(archive.read("manifest.json"))
        assert manifest["status"] == "READY"
        assert manifest["resources"] == []

    live_worker.run_control_task(MAINTENANCE_TASK)
    live_worker.wait_for(
        lambda: BackgroundJob.objects.filter(
            pk=job.pk, notification_state="sent"
        ).exists()
    )
    JobArtifact.objects.filter(pk=artifact.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert api.get(path).status_code == HTTPStatus.GONE
    live_worker.run_control_task(CLEANUP_TASK)
    artifact.refresh_from_db()
    assert artifact.deleted_at is not None
    with pytest.raises(ClientError) as missing:
        ExportStorage().connection.meta.client.head_object(
            Bucket=TEST_BUCKET, Key=artifact.object_key
        )
    assert missing.value.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}


def test_live_duplicate_delivery_preserves_success(live_worker: LiveWorker) -> None:
    job: BackgroundJob
    job, _ = request_export(VerifiedUserFactory.create())
    attempt: JobAttempt = live_worker.wait_ready(job)
    artifact: JobArtifact = JobArtifact.objects.get(job=job)
    result: TaskResult = TaskResult.objects.get(task_id=str(attempt.task_id))
    original_result: str | None = result.result
    original_completion: datetime = result.date_done
    live_worker.application.send_task(
        GENERATION_TASK,
        args=[str(job.id), str(attempt.id)],
        task_id=str(attempt.task_id),
        queue="exports",
    )
    live_worker.wait_for(
        lambda: any(
            str(attempt.task_id) in line and "ignored" in line.lower()
            for line in live_worker.log_path.read_text(encoding="utf-8").splitlines()
        )
    )
    result.refresh_from_db()
    assert result.status == "SUCCESS"
    assert result.result == original_result
    assert result.date_done == original_completion
    assert JobArtifact.objects.get(job=job).pk == artifact.pk
    assert job.attempts.count() == 1


def test_live_broker_failure_keeps_request_for_maintenance(
    live_worker: LiveWorker,
) -> None:
    user: User = VerifiedUserFactory.create()
    job: BackgroundJob
    created: bool
    # Reserve, but do not listen on, an unused local port. The request experiences
    # a real connection refusal without stopping any existing Redis process.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as unavailable:
        unavailable.bind(("127.0.0.1", 0))
        address: tuple[str, int] = unavailable.getsockname()
        with _publisher(f"redis://127.0.0.1:{address[1]}/0"):
            job, created = request_export(user)
    attempt: JobAttempt = job.attempts.get()
    assert created
    job.refresh_from_db()
    assert job.state == JobState.RETRY_WAIT
    assert attempt.state == JobState.FAILED
    assert attempt.dispatched_at is None
    BackgroundJob.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now())
    live_worker.run_control_task(MAINTENANCE_TASK)
    live_worker.wait_ready(job)
    assert JobArtifact.objects.filter(job=job).exists()
    assert JobArtifact.objects.get(job=job).attempt_id != attempt.pk


def test_live_worker_death_recovers_with_a_new_attempt(live_worker: LiveWorker) -> None:
    user: User = VerifiedUserFactory.create()
    job: BackgroundJob
    # An actual database lock holds the worker immediately after its durable
    # claim. This makes the process-death boundary deterministic without mocks
    # or timing assumptions about how long a small archive takes to generate.
    with psycopg.connect(**connection.get_connection_params()) as blocked_results:
        blocked_results.execute(
            "LOCK TABLE django_celery_results_taskresult IN ACCESS EXCLUSIVE MODE"
        )
        job, _ = request_export(user)
        live_worker.wait_for(
            lambda: BackgroundJob.objects.filter(
                pk=job.pk, state=JobState.RUNNING
            ).exists()
        )
        os.killpg(live_worker.process.pid, signal.SIGKILL)
        live_worker.process.wait(timeout=10)

    abandoned: JobAttempt = job.attempts.get()
    assert abandoned.state == JobState.RUNNING
    assert not JobArtifact.objects.filter(job=job).exists()
    JobAttempt.objects.filter(pk=abandoned.pk).update(
        deadline_at=timezone.now() - timedelta(minutes=6)
    )
    live_worker.restart()
    live_worker.run_control_task(MAINTENANCE_TASK)
    job.refresh_from_db()
    abandoned.refresh_from_db()
    assert job.state == JobState.RETRY_WAIT
    assert abandoned.state == JobState.FAILED

    BackgroundJob.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now())
    live_worker.run_control_task(MAINTENANCE_TASK)
    replacement: JobAttempt = live_worker.wait_ready(job)
    assert replacement.pk != abandoned.pk
    assert replacement.number == abandoned.number + 1
    artifact: JobArtifact = JobArtifact.objects.get(job=job)
    assert artifact.attempt_id == replacement.pk
    assert artifact.object_key != abandoned.object_key
    with pytest.raises(ClientError) as missing:
        ExportStorage().connection.meta.client.head_object(
            Bucket=TEST_BUCKET, Key=abandoned.object_key
        )
    assert missing.value.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}
