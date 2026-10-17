"""Exercise scheduling, lease failures, and signals through real service APIs."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from itertools import pairwise
from pathlib import Path
from threading import Timer
from typing import TYPE_CHECKING
from typing import Any

import psycopg
import pytest
from celery import Celery
from celery.signals import before_task_publish
from django.conf import settings
from django.db import connection
from django.utils import timezone
from django_celery_beat.models import IntervalSchedule
from django_celery_beat.models import PeriodicTask
from django_celery_beat.schedulers import ModelEntry
from kombu import Exchange
from kombu import Producer
from kombu import Queue
from kombu.exceptions import OperationalError
from redis import Redis

from speleodb.background_jobs.lease import BEAT_LOCK_ID
from speleodb.background_jobs.lease import LOCK_MAX_ATTEMPTS
from speleodb.background_jobs.lease import LOCK_WAIT_SECONDS
from speleodb.background_jobs.lease import SchedulerLease
from speleodb.background_jobs.lease import SchedulerLeaseLostError
from speleodb.background_jobs.scheduler import ExponentialBackoffDatabaseScheduler
from speleodb.testing.celery import isolated_test_broker_url
from speleodb.testing.database import postgres_test_database_url

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator

    from celery.beat import ScheduleEntry

pytestmark = pytest.mark.django_db(transaction=True)
PROCESS_TIMEOUT_SECONDS: int = 20


@pytest.fixture
def postgres_parameters() -> dict[str, Any]:
    if connection.vendor != "postgresql":
        pytest.skip("Scheduler integration requires isolated PostgreSQL.")
    assert str(connection.settings_dict["NAME"]).startswith("test_")
    return connection.get_connection_params()


@pytest.fixture
def lease(postgres_parameters: dict[str, Any]) -> Iterator[SchedulerLease]:
    owner = SchedulerLease(postgres_parameters)
    owner.acquire()
    try:
        yield owner
    finally:
        owner.close()


@dataclass
class SchedulerRuntime:
    app: Celery
    scheduler: ExponentialBackoffDatabaseScheduler
    task: PeriodicTask
    queue: str


@contextmanager
def scheduler_runtime(
    lease: SchedulerLease, *, broker_url: str = "memory://"
) -> Iterator[SchedulerRuntime]:
    queue = f"scheduler-test-{uuid.uuid4().hex}"
    app = Celery(queue, fixups=[], set_as_current=False)
    app.conf.update(
        broker_url=broker_url,
        broker_read_url=broker_url,
        broker_write_url=broker_url,
        broker_transport_options={"socket_timeout": 0.2, "socket_connect_timeout": 1},
        broker_connection_max_retries=2,
        broker_retry_base_delay_seconds=0.1,
        broker_retry_max_delay_seconds=0.2,
        task_default_queue=queue,
        task_send_sent_event=False,
        result_backend=None,
        result_expires=None,
    )
    interval = IntervalSchedule.objects.create(every=60, period="seconds")
    task = PeriodicTask.objects.create(
        name=queue,
        task=f"scheduler_test.{uuid.uuid4().hex}",
        interval=interval,
        queue=queue,
        last_run_at=timezone.now() - timedelta(seconds=120),
    )
    scheduler = ExponentialBackoffDatabaseScheduler(app=app, lease=lease)
    try:
        yield SchedulerRuntime(app, scheduler, task, queue)
    finally:
        scheduler.close()
        app.close()


@pytest.fixture
def runtime(lease: SchedulerLease) -> Iterator[SchedulerRuntime]:
    with scheduler_runtime(lease) as current:
        yield current


@pytest.fixture
def isolated_redis() -> Iterator[tuple[str, Redis]]:
    broker_url = os.environ.get("TEST_CELERY_BROKER_URL", "")
    if not broker_url:
        pytest.skip("Set TEST_CELERY_BROKER_URL to the isolated Redis service.")
    broker_url = isolated_test_broker_url()
    client = Redis.from_url(broker_url, socket_timeout=2, socket_connect_timeout=1)
    assert client.ping()
    try:
        yield broker_url, client
    finally:
        client.close()


def _wait_until(predicate: Callable[[], bool], *, timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    pytest.fail("Timed out waiting for the real scheduler/database operation.")


@contextmanager
def beat_process(
    tmp_path: Path, *, broker_url: str = "memory://"
) -> Iterator[tuple[subprocess.Popen[str], Path, str]]:
    application_name = f"beat-test-{uuid.uuid4().hex}"
    environment = os.environ.copy()
    environment.update(
        DJANGO_SETTINGS_MODULE="invalid.inherited.settings",
        DJANGO_READ_DOT_ENV_FILE="false",
        DJANGO_SECRET_KEY="isolated-scheduler-runtime-test",  # noqa: S106 - test-only key.
        DATABASE_URL=postgres_test_database_url(),
        USE_DOCKER="false",
        CELERY_BROKER_URL=broker_url,
        CELERY_SKIP_CHECKS="false",
        PGAPPNAME=application_name,
    )
    command = [sys.executable, "-m", "speleodb.background_jobs.beat"]
    log_path = tmp_path / f"{application_name}.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(  # noqa: S603 - fixed Python/module entrypoint.
            command,
            env=environment,
            cwd=settings.BASE_DIR,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            yield process, log_path, application_name
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=PROCESS_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=PROCESS_TIMEOUT_SECONDS)


def _activity(application_name: str) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pid, query, wait_event_type, query_start FROM pg_stat_activity "
            "WHERE application_name = %s",
            [application_name],
        )
        return list(cursor.fetchall())


def _owns_lock(application_name: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_locks l JOIN pg_stat_activity a "
            "ON l.pid = a.pid WHERE a.application_name = %s "
            "AND l.locktype = 'advisory' AND l.objid = %s AND l.granted)",
            [application_name, BEAT_LOCK_ID],
        )
        return bool(cursor.fetchone()[0])


def test_standby_acquires_lock_after_previous_scheduler_exits(
    postgres_parameters: dict[str, Any],
) -> None:
    previous = SchedulerLease(postgres_parameters)
    previous.acquire()
    replacement = SchedulerLease(postgres_parameters)
    release = Timer(0.1, previous.close)
    release.start()
    try:
        replacement.acquire()
        replacement.assert_owned()
        assert previous.connection is not None
        assert previous.connection.closed
        assert replacement.connection is not connection.connection
        connection.close()
        replacement.assert_owned()
    finally:
        release.join()
        previous.close()
        replacement.close()


@pytest.mark.parametrize(
    ("task_name", "ignore_result", "task_args"),
    [
        ("speleodb.background_jobs.tasks.maintain_background_jobs", True, []),
        ("speleodb.background_jobs.tasks.delete_expired_artifacts", True, []),
        ("celery.backend_cleanup", True, []),
        ("speleodb.users.tasks.get_users_count", False, []),
        (
            "speleodb.gis.tasks.generate_project_geojson",
            False,
            ["a" * 40, str(uuid.uuid4())],
        ),
        ("speleodb.surveys.tasks.refresh_project_geojson", False, [str(uuid.uuid4())]),
    ],
)
@pytest.mark.parametrize("advance", [False, True])
def test_scheduler_result_policy_preserves_original_entry_options(
    runtime: SchedulerRuntime,
    task_name: str,
    ignore_result: bool,
    task_args: list[str],
    advance: bool,
) -> None:
    # The first change check establishes django-celery-beat's timestamp. Prime
    # it before changing the row so the next read actually reloads this task.
    assert runtime.scheduler.schedule[runtime.task.name].task == runtime.task.task
    runtime.task.task = task_name
    runtime.task.args = json.dumps(task_args)
    runtime.task.save(update_fields=["task", "args"])
    entry: ScheduleEntry = runtime.scheduler.schedule[runtime.task.name]
    assert isinstance(entry, ModelEntry)
    assert entry.task == task_name
    assert entry.options is not None
    entry.options["ignore_result"] = False
    original_options: dict[str, Any] = entry.options
    options_before: dict[str, Any] = original_options.copy()
    observed_policies: list[dict[str, Any]] = []

    def observe_policy(retry_policy: dict[str, Any], **kwargs: Any) -> None:
        observed_policies.append(retry_policy)

    before_task_publish.connect(observe_policy, sender=task_name, weak=False)
    try:
        result = runtime.scheduler.apply_async(entry, advance=advance)
    finally:
        before_task_publish.disconnect(observe_policy, sender=task_name)

    assert entry.options is original_options
    assert entry.options == options_before
    assert len(observed_policies) == 1
    assert callable(observed_policies[0]["errback"])
    assert callable(observed_policies[0]["on_revive"])
    runtime.scheduler.sync()
    runtime.task.refresh_from_db()
    assert runtime.task.total_run_count == int(advance)
    with (
        runtime.app.connection_for_read() as broker,
        broker.SimpleQueue(runtime.queue) as queue,
    ):
        message = queue.get(block=False)
        assert message.headers["task"] == task_name
        assert message.headers["id"] == result.id
        assert message.payload[0] == task_args
        # Kombu's headers stub permits strings, but Celery sends booleans.
        received_ignore_result: object = message.headers["ignore_result"]
        assert received_ignore_result is ignore_result
        message.ack()


@pytest.mark.parametrize("failure", ["close", "unlock", "terminate"])
def test_lost_lease_cannot_recover_or_publish_again(
    lease: SchedulerLease, runtime: SchedulerRuntime, failure: str
) -> None:
    assert lease.connection is not None
    if failure == "close":
        lease.connection.close()
    elif failure == "unlock":
        lease.connection.execute("SELECT pg_advisory_unlock_all()")
    else:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_terminate_backend(%s)", [lease.connection.info.backend_pid]
            )
            assert cursor.fetchone()[0]
    with pytest.raises(SchedulerLeaseLostError):
        runtime.scheduler.tick()
    assert lease.lost
    assert not lease.active
    with pytest.raises(SchedulerLeaseLostError):
        lease.assert_owned()
    with pytest.raises(RuntimeError, match="cannot be reacquired"):
        lease.acquire()
    runtime.task.refresh_from_db()
    assert runtime.task.total_run_count == 0
    with (
        runtime.app.connection_for_read() as broker,
        broker.SimpleQueue(runtime.queue) as queue,
    ):
        assert queue.qsize() == 0


def test_tick_publishes_real_message_and_preserves_entry_options(
    runtime: SchedulerRuntime,
) -> None:
    entry = runtime.scheduler.schedule[runtime.task.name]
    options = entry.options
    runtime.scheduler.tick()
    runtime.scheduler.sync()
    runtime.task.refresh_from_db()
    assert runtime.task.total_run_count == 1
    assert entry.options is options
    with (
        runtime.app.connection_for_read() as broker,
        broker.SimpleQueue(runtime.queue) as queue,
    ):
        message = queue.get(block=False)
        assert message.headers["task"] == runtime.task.task
        # Kombu's stub narrows header values to strings, although Celery uses
        # JSON booleans here. Keep the received value's runtime type explicit.
        ignore_result: object = message.headers["ignore_result"]
        assert ignore_result is False
        message.ack()
        assert queue.qsize() == 0


def test_scheduler_connection_failure_obeys_budget(
    lease: SchedulerLease,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # A bound but non-listening socket guarantees refusal without a race for
    # an otherwise-unused port and without replacing Kombu's connection API.
    with socket.socket() as refused:
        refused.bind(("127.0.0.1", 0))
        broker_url = f"redis://127.0.0.1:{refused.getsockname()[1]}/0"
        with scheduler_runtime(lease, broker_url=broker_url) as current:
            started = time.monotonic()
            with pytest.raises(OperationalError):
                current.scheduler.tick()
            assert time.monotonic() - started >= sum((0.1, 0.2))
            failures = [
                record
                for record in caplog.records
                if record.name == "speleodb.background_jobs.broker"
            ]
            assert len(failures) == 3  # noqa: PLR2004
            assert "attempt 3/3" in failures[-1].getMessage()
            lease.assert_owned()


def test_scheduler_connection_recovers_through_real_failover(
    lease: SchedulerLease,
    isolated_redis: tuple[str, Redis],
) -> None:
    broker_url, client = isolated_redis
    with socket.socket() as refused:
        refused.bind(("127.0.0.1", 0))
        unavailable = f"redis://127.0.0.1:{refused.getsockname()[1]}/0"
        with scheduler_runtime(
            lease, broker_url=f"{unavailable};{broker_url}"
        ) as current:
            current.scheduler.tick()
            current.scheduler.sync()
            payload = client.lpop(current.queue)
            assert isinstance(payload, bytes | str)
            message = json.loads(payload)
            assert message["headers"]["task"] == current.task.task
            current.task.refresh_from_db()
            assert current.task.total_run_count == 1
            client.delete(current.queue, f"_kombu.binding.{current.queue}")


@pytest.mark.parametrize("predeclare", [False, True])
def test_real_broker_retries_cannot_publish_after_lease_loss(
    lease: SchedulerLease,
    isolated_redis: tuple[str, Redis],
    caplog: pytest.LogCaptureFixture,
    predeclare: bool,
) -> None:
    broker_url, client = isolated_redis
    with scheduler_runtime(lease, broker_url=broker_url) as current:
        if predeclare:
            channel = current.scheduler.producer.channel
            assert channel is not None
            current.app.amqp.queues[current.queue].bind(channel).declare()
        policies: list[dict[str, Any]] = []
        pauses: list[bool] = []
        owner = lease.connection
        assert owner is not None

        def interrupt_publication(
            sender: str, retry_policy: dict[str, Any], **kwargs: Any
        ) -> None:
            policies.append(retry_policy)
            owner.execute("SELECT pg_advisory_unlock_all()")
            # Redis's administrative API creates a real write timeout; the
            # server resumes automatically without replacing any client method.
            pauses.append(client.client_pause(1000, mode="WRITE"))

        before_task_publish.connect(
            interrupt_publication, sender=current.task.task, weak=False
        )
        try:
            with pytest.raises(SchedulerLeaseLostError):
                current.scheduler.tick()
        finally:
            before_task_publish.disconnect(
                interrupt_publication, sender=current.task.task
            )
            client.client_unpause()
        assert lease.lost
        # Celery signals catch receiver exceptions. Assert the administrative
        # operation completed outside the receiver, where failure cannot hide.
        assert pauses == [True]
        assert "Message Error" in caplog.text
        assert policies
        assert callable(policies[0]["errback"])
        assert callable(policies[0]["on_revive"])
        assert client.llen(current.queue) == 0
        current.task.refresh_from_db()
        assert current.task.total_run_count == 0
        client.delete(current.queue, f"_kombu.binding.{current.queue}")


def test_real_kombu_connection_revival_rechecks_ownership(
    lease: SchedulerLease,
    isolated_redis: tuple[str, Redis],
) -> None:
    broker_url, client = isolated_redis
    policies: list[dict[str, Any]] = []

    def observe_policy(retry_policy: dict[str, Any], **kwargs: Any) -> None:
        policies.append(retry_policy)

    with scheduler_runtime(lease, broker_url=broker_url) as current:
        before_task_publish.connect(
            observe_policy, sender=current.task.task, weak=False
        )
        try:
            current.scheduler.tick()
        finally:
            before_task_publish.disconnect(observe_policy, sender=current.task.task)
        assert client.lpop(current.queue) is not None
        assert policies
        assert lease.connection is not None
        lease.connection.execute("SELECT pg_advisory_unlock_all()")
        retry_queue = f"scheduler-revival-{uuid.uuid4().hex}"
        with current.app.connection_for_write() as broker:
            producer = Producer(broker)
            # Establish the real channel before inducing the outage. Lazy
            # initial-channel creation has its own internal connection retries
            # and can otherwise recover without reaching Connection.ensure.
            assert producer.channel is not None
            # Exercise Kombu's actual revival callback separately from errback.
            # Queue declaration hits a genuine Redis write timeout before any
            # message is sent; reconnect succeeds while writes remain paused.
            guarded_publish = broker.ensure(
                producer,
                producer.publish,
                on_revive=policies[0]["on_revive"],
                max_retries=2,
            )
            client.client_pause(1000, mode="WRITE")
            try:
                with pytest.raises(SchedulerLeaseLostError):
                    guarded_publish(
                        {"probe": True},
                        routing_key=retry_queue,
                        declare=[Queue(retry_queue, exchange=Exchange(retry_queue))],
                    )
            finally:
                client.client_unpause()
        assert lease.lost
        assert client.llen(retry_queue) == 0
        client.delete(
            current.queue,
            f"_kombu.binding.{current.queue}",
            retry_queue,
            f"_kombu.binding.{retry_queue}",
        )


def test_close_syncs_once_and_finalizers_cannot_overwrite_new_owner_state(
    runtime: SchedulerRuntime,
    lease: SchedulerLease,
) -> None:
    entry = runtime.scheduler.schedule[runtime.task.name]
    runtime.scheduler.reserve(entry)
    runtime.scheduler.close()
    runtime.task.refresh_from_db()
    assert runtime.task.total_run_count == 1
    lease.close()
    PeriodicTask.objects.filter(pk=runtime.task.pk).update(total_run_count=77)
    runtime.scheduler.reserve(entry)
    runtime.scheduler.close()
    runtime.scheduler.sync()
    runtime.task.refresh_from_db()
    assert runtime.task.total_run_count == 77  # noqa: PLR2004


@pytest.mark.parametrize("state", ["lost", "closed", "lazy"])
def test_sync_skips_unowned_and_lazy_schedulers(
    runtime: SchedulerRuntime,
    lease: SchedulerLease,
    state: str,
) -> None:
    scheduler = runtime.scheduler
    if state == "lazy":
        scheduler = ExponentialBackoffDatabaseScheduler(
            app=runtime.app, lease=lease, lazy=True
        )
    try:
        entry = runtime.scheduler.schedule[runtime.task.name]
        scheduler.reserve(entry)
        if state == "lost":
            assert lease.connection is not None
            lease.connection.close()
        elif state == "closed":
            lease.close()
        scheduler.sync()
        runtime.task.refresh_from_db()
        assert runtime.task.total_run_count == 0
    finally:
        scheduler.close()


def test_standby_exhausts_real_finite_lock_budget(
    lease: SchedulerLease,
    tmp_path: Path,
) -> None:
    with beat_process(tmp_path) as (process, log_path, application_name):
        observed_queries: list[Any] = []
        deadline = time.monotonic() + 180
        while process.poll() is None and time.monotonic() < deadline:
            for _, query, _, query_start in _activity(application_name):
                if (
                    "pg_try_advisory_lock" in query
                    and query_start not in observed_queries
                ):
                    observed_queries.append(query_start)
            time.sleep(0.1)
        assert process.wait(timeout=PROCESS_TIMEOUT_SECONDS) != 0
        assert f"after {LOCK_MAX_ATTEMPTS} attempts" in log_path.read_text()
        # The final query can finish and disconnect between observations. The
        # first five stable idle sessions expose the actual exponential waits.
        assert len(observed_queries) >= LOCK_MAX_ATTEMPTS - 1
        for index, (before, after) in enumerate(pairwise(observed_queries)):
            assert (after - before).total_seconds() == pytest.approx(
                LOCK_WAIT_SECONDS * 2**index, abs=2
            )
    lease.assert_owned()


def test_sigterm_interrupts_standby_wait_without_releasing_previous_owner(
    lease: SchedulerLease,
    tmp_path: Path,
) -> None:
    with beat_process(tmp_path) as (process, log_path, application_name):
        _wait_until(
            lambda: any(
                "pg_try_advisory_lock" in row[1] for row in _activity(application_name)
            )
        )
        started = time.monotonic()
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=PROCESS_TIMEOUT_SECONDS) == 0, log_path.read_text()
        assert time.monotonic() - started < LOCK_WAIT_SECONDS
        lease.assert_owned()
        _wait_until(lambda: not _activity(application_name))


def test_sigterm_during_real_scheduler_database_initialization(
    postgres_parameters: dict[str, Any],
    tmp_path: Path,
) -> None:
    with psycopg.connect(**postgres_parameters) as blocker:
        blocker.execute(
            "LOCK TABLE django_celery_beat_periodictask IN ACCESS EXCLUSIVE MODE"
        )
        with beat_process(tmp_path) as (process, log_path, application_name):
            _wait_until(
                lambda: any(
                    row[2] == "Lock" and "django_celery_beat_periodictask" in row[1]
                    for row in _activity(application_name)
                )
            )
            assert _owns_lock(application_name)
            process.send_signal(signal.SIGTERM)
            assert process.wait(timeout=PROCESS_TIMEOUT_SECONDS) == 0, (
                log_path.read_text()
            )
            assert not _owns_lock(application_name)
            assert not _activity(application_name)


def test_launcher_releases_lease_after_real_invalid_broker_failure(
    postgres_parameters: dict[str, Any],
    tmp_path: Path,
) -> None:
    with beat_process(tmp_path, broker_url="invalid-transport://") as (
        process,
        log_path,
        application_name,
    ):
        assert process.wait(timeout=PROCESS_TIMEOUT_SECONDS) != 0
        assert "invalid-transport" in log_path.read_text()
        assert not _owns_lock(application_name)
    replacement = SchedulerLease(postgres_parameters)
    try:
        replacement.acquire()
        replacement.assert_owned()
    finally:
        replacement.close()


def test_sigterm_syncs_actual_publication_before_releasing_lock(
    postgres_parameters: dict[str, Any],
    isolated_redis: tuple[str, Redis],
    tmp_path: Path,
) -> None:
    broker_url, client = isolated_redis
    queue = f"scheduler-stop-{uuid.uuid4().hex}"
    interval = IntervalSchedule.objects.create(every=60, period="seconds")
    task = PeriodicTask.objects.create(
        name=queue,
        task="scheduler_test.shutdown",
        interval=interval,
        queue=queue,
        last_run_at=timezone.now() - timedelta(seconds=120),
    )
    try:
        with beat_process(tmp_path, broker_url=broker_url) as (
            process,
            log_path,
            application_name,
        ):
            _wait_until(lambda: bool(client.llen(queue)))
            assert _owns_lock(application_name)
            process.terminate()
            assert process.wait(timeout=PROCESS_TIMEOUT_SECONDS) == 0, (
                log_path.read_text()
            )
            assert not _owns_lock(application_name)
            task.refresh_from_db()
            assert task.total_run_count == 1
            message = client.lpop(queue)
            assert isinstance(message, bytes | str)
            assert json.loads(message)["headers"]["task"] == task.task
            assert client.llen(queue) == 0
    finally:
        client.delete(queue, f"_kombu.binding.{queue}")


def test_launcher_runs_in_one_process_and_one_thread(
    postgres_parameters: dict[str, Any],
    tmp_path: Path,
) -> None:
    with beat_process(tmp_path) as (process, log_path, application_name):
        _wait_until(lambda: _owns_lock(application_name))
        process_path = Path(f"/proc/{process.pid}")
        command = (process_path / "cmdline").read_bytes()
        assert b"-m\x00speleodb.background_jobs.beat" in command
        assert not (process_path / f"task/{process.pid}/children").read_text().strip()
        status = (process_path / "status").read_text()
        assert (
            next(
                line for line in status.splitlines() if line.startswith("Threads:")
            ).split()[1]
            == "1"
        )
        process.terminate()
        assert process.wait(timeout=PROCESS_TIMEOUT_SECONDS) == 0, log_path.read_text()
        assert not _owns_lock(application_name)
