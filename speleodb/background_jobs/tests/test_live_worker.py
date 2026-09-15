"""Opt-in PostgreSQL/Redis/RustFS tests with an actual Celery subprocess."""

from __future__ import annotations

import io
import os
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
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import quote
from urllib.parse import urlencode
from urllib.parse import urlsplit
from zipfile import ZipFile

import orjson
import psycopg
import pytest
import requests
from allauth.account.models import EmailAddress
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
from speleodb.users.tasks import get_users_count
from speleodb.users.tests.factories import UserFactory
from speleodb.utils.s3_storages import ExportStorage

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator
    from pathlib import Path
    from urllib.parse import SplitResult

    from django.http import HttpResponse

    from speleodb.users.models import User

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        os.environ.get("EXPORTS_LIVE_WORKER_TESTS") != "1",
        reason="Set EXPORTS_LIVE_WORKER_TESTS=1 to use isolated live services.",
    ),
]

WAIT_SECONDS: int = 45
TEST_BUCKET: str = "speleodb-user-artifacts-test"
MAINTENANCE_TASK: str = "speleodb.background_jobs.tasks.maintain_background_jobs"
CLEANUP_TASK: str = "speleodb.background_jobs.tasks.delete_expired_artifacts"
TEST_BROKER_PORT: int = 6381
REDIS_PORT: int = 6379


@contextmanager
def _publisher(broker_url: str) -> Iterator[Celery]:
    """Use a fresh real connection pool when switching between live/dead brokers."""
    previous: Celery = get_current_app()
    previous_broker: str | None = os.environ.get("CELERY_BROKER_URL")
    os.environ["CELERY_BROKER_URL"] = broker_url
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
        try:
            yield application
        finally:
            previous.set_current()
            if previous_broker is None:
                os.environ.pop("CELERY_BROKER_URL", None)
            else:
                os.environ["CELERY_BROKER_URL"] = previous_broker


def _test_database_url() -> str:
    database: dict[str, Any] = connection.settings_dict
    assert connection.vendor == "postgresql", "Live workers require PostgreSQL."
    assert str(database["NAME"]).startswith("test_"), (
        "Refusing to run a worker against a database without the test_ prefix."
    )
    host: str = str(database.get("HOST") or "localhost")
    assert not host.startswith("/"), "Use a TCP PostgreSQL address for live tests."
    authority: str = f"[{host}]" if ":" in host else host
    user: str = quote(str(database.get("USER") or ""), safe="")
    password: str = quote(str(database.get("PASSWORD") or ""), safe="")
    name: str = quote(str(database["NAME"]), safe="")
    port: str = str(database.get("PORT") or "5432")
    options: dict[str, str] = {
        key: str(value)
        for key, value in database.get("OPTIONS", {}).items()
        if key in {"sslmode", "sslrootcert", "sslcert", "sslkey", "options"}
    }
    query: str = f"?{urlencode(options)}" if options else ""
    return f"postgresql://{user}:{password}@{authority}:{port}/{name}{query}"


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

    def run_control_task(self, name: str) -> None:
        task_id: str = str(uuid.uuid4())
        self.application.send_task(name, queue="background_control", task_id=task_id)
        self.wait_for(
            lambda: TaskResult.objects.filter(
                task_id=task_id, status="SUCCESS"
            ).exists()
        )


@pytest.fixture
def live_worker(tmp_path: Path, transactional_db: None) -> Iterator[LiveWorker]:
    broker_url: str = os.environ.get("TEST_CELERY_BROKER_URL", "")
    broker: SplitResult = urlsplit(broker_url)
    allowed_broker: bool = (
        broker.hostname in {"localhost", "127.0.0.1"}
        and broker.port == TEST_BROKER_PORT
    ) or (broker.hostname == "celery-test-redis" and broker.port == REDIS_PORT)
    assert broker.scheme == "redis"
    assert allowed_broker, (
        "Use the dedicated celery-test-redis service; development brokers are refused."
    )
    assert settings.AWS_STORAGE_BUCKET_NAME == TEST_BUCKET
    assert urlsplit(settings.AWS_S3_ENDPOINT_URL).hostname in {
        "localhost",
        "127.0.0.1",
        "rustfs",
    }, "Use the local RustFS test bucket."
    database_url: str = _test_database_url()
    ExportStorage().connection.meta.client.head_bucket(Bucket=TEST_BUCKET)
    hostname: str = f"exports-integration-{uuid.uuid4()}@localhost"
    environment: dict[str, str] = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.test",
            "TEST_DATABASE_URL": database_url,
            "TEST_CELERY_BROKER_URL": broker_url,
            "CELERY_BROKER_URL": broker_url,
            "EXPORTS_SCRATCH_DIR": str(tmp_path / "scratch"),
            "PYTHONUNBUFFERED": "1",
        }
    )
    log_path: Path = tmp_path / "celery-worker.log"
    with _publisher(broker_url) as application, log_path.open("wb") as log:
        with application.connection_for_write() as broker_connection:
            broker_connection.ensure_connection(max_retries=0)
        process: subprocess.Popen[bytes] = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "config.celery_app",
                "worker",
                "--pool",
                "solo",
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
                "--events",
                "--without-gossip",
                "--without-mingle",
            ],
            env=environment,
            cwd=settings.BASE_DIR,
            stdout=log,
            stderr=subprocess.STDOUT,
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
                worker.process.kill()
                worker.process.wait(timeout=5)
            # Only delete object keys created in this transaction-isolated test DB.
            for attempt in JobAttempt.objects.exclude(object_key="").iterator():
                delete_archive(key=attempt.object_key)


def _verified_user() -> User:
    user: User = UserFactory.create()
    EmailAddress.objects.update_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )
    return user


def test_live_worker_consumes_existing_tasks_without_an_explicit_queue(
    live_worker: LiveWorker,
) -> None:
    _verified_user()
    expected_count: int = get_users_count()
    task_id: str = str(uuid.uuid4())
    live_worker.application.send_task(
        "speleodb.users.tasks.get_users_count", task_id=task_id
    )
    live_worker.wait_for(
        lambda: TaskResult.objects.filter(task_id=task_id, status="SUCCESS").exists()
    )
    assert orjson.loads(TaskResult.objects.get(task_id=task_id).result or "null") == (
        expected_count
    )


def test_live_export_download_notification_and_expiration(
    live_worker: LiveWorker,
) -> None:
    user: User = _verified_user()
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
            "gis_layers/",
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
    job, _ = request_export(_verified_user())
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
    user: User = _verified_user()
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
    user: User = _verified_user()
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
        live_worker.process.kill()
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
