"""Exercise consumer retries with real Celery construction and broker sockets."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from celery import Celery
from celery.result import denied_join_result
from celery.worker import WorkController
from django.db import connections
from kombu import Connection
from kombu.exceptions import OperationalError

from speleodb.background_jobs.consumer import ExponentialBackoffConsumer

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

RETRY_BASE_SECONDS: float = 0.01
RETRY_MAX_SECONDS: float = 0.3
STARTUP_TIMEOUT_SECONDS: float = 15.0
SHUTDOWN_TIMEOUT_SECONDS: float = 5.0


@pytest.fixture
def consumer(transactional_db: None) -> Iterator[ExponentialBackoffConsumer]:
    # A real worker initializes Django's process-wide database lifecycle hooks.
    # Release pytest's connection first, outside an enclosing atomic test.
    connections.close_all()
    with (
        Celery(
            "consumer-retry-tests", broker="memory://", fixups=[], set_as_current=False
        ) as application,
        denied_join_result(),
    ):
        application.conf.update(
            broker_read_url="memory://",
            broker_write_url="memory://",
            worker_consumer=(
                "speleodb.background_jobs.consumer:ExponentialBackoffConsumer"
            ),
            broker_connection_retry_on_startup=True,
            broker_connection_retry=True,
            broker_connection_max_retries=5,
            broker_retry_base_delay_seconds=RETRY_BASE_SECONDS,
            broker_retry_max_delay_seconds=RETRY_MAX_SECONDS,
        )
        controller = WorkController(
            app=application,
            pool="prefork",
            concurrency=1,
            use_eventloop=False,
            without_gossip=True,
            without_mingle=True,
            without_heartbeat=True,
        )
        # Celery's bootstep installs this attribute during normal construction;
        # the upstream WorkController stub does not declare it.
        current_consumer: object = controller.consumer  # type: ignore[attr-defined]
        assert isinstance(current_consumer, ExponentialBackoffConsumer)
        try:
            yield current_consumer
        finally:
            controller.stop()


@pytest.fixture
def unavailable_broker() -> Iterator[str]:
    # A bound, non-listening socket reserves a real port and reliably refuses
    # connections without risking a port another process could acquire.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        yield f"redis://127.0.0.1:{reserved.getsockname()[1]}/0"


def retry_delays(caplog: pytest.LogCaptureFixture) -> list[float]:
    delays: list[float] = []
    for record in caplog.records:
        if record.name == "speleodb.utils.helpers":
            assert isinstance(record.args, tuple)
            delay = record.args[3]
            assert isinstance(delay, float)
            delays.append(delay)
    return delays


def connection_attempts(caplog: pytest.LogCaptureFixture) -> int:
    return sum(
        record.name == "speleodb.background_jobs.broker" for record in caplog.records
    )


def test_broker_retries_stop_at_budget_with_exponential_delays(
    consumer: ExponentialBackoffConsumer,
    unavailable_broker: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with Connection(unavailable_broker, connect_timeout=0.1) as broker:
        started: float = time.monotonic()
        with caplog.at_level("DEBUG"), pytest.raises(OperationalError):
            consumer.ensure_connected(broker)
        elapsed: float = time.monotonic() - started
        assert not broker.connected
    expected: list[float] = [0.01, 0.02, 0.04, 0.08, 0.16]
    assert connection_attempts(caplog) == 6  # noqa: PLR2004
    assert retry_delays(caplog) == expected
    assert elapsed >= sum(expected)


def test_broker_success_resets_state_and_retains_failover(
    consumer: ExponentialBackoffConsumer,
    unavailable_broker: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with Connection(f"{unavailable_broker};memory://", connect_timeout=0.1) as broker:
        with caplog.at_level("DEBUG"):
            assert consumer.ensure_connected(broker) is broker
        assert broker.connected
        assert broker.transport.driver_type == "memory"
    assert retry_delays(caplog) == [RETRY_BASE_SECONDS]
    assert consumer.first_connection_attempt is False
    assert consumer.broker_connection_retry_attempt == 0


@pytest.mark.parametrize(
    ("first_connection", "startup_retry", "runtime_retry"),
    [(True, False, True), (False, True, False), (True, None, False)],
)
def test_disabled_retry_does_not_fail_over_after_connection_refusal(  # noqa: PLR0917
    consumer: ExponentialBackoffConsumer,
    unavailable_broker: str,
    caplog: pytest.LogCaptureFixture,
    first_connection: bool,
    startup_retry: bool | None,
    runtime_retry: bool,
) -> None:
    if not first_connection:
        with Connection("memory://") as initial:
            consumer.ensure_connected(initial)
    consumer.app.conf.update(
        broker_connection_retry_on_startup=startup_retry,
        broker_connection_retry=runtime_retry,
    )
    with Connection(f"{unavailable_broker};memory://", connect_timeout=0.1) as broker:
        with pytest.raises(broker.connection_errors):
            consumer.ensure_connected(broker)
        assert not broker.connected
        assert broker.transport.driver_type == "redis"
    assert connection_attempts(caplog) == 0


@pytest.mark.parametrize(
    ("first_connection", "startup_retry", "runtime_retry"),
    [(True, True, False), (False, False, True), (True, None, True)],
)
def test_enabled_retry_respects_startup_and_runtime_flags(  # noqa: PLR0917
    consumer: ExponentialBackoffConsumer,
    unavailable_broker: str,
    caplog: pytest.LogCaptureFixture,
    first_connection: bool,
    startup_retry: bool | None,
    runtime_retry: bool,
) -> None:
    if not first_connection:
        with Connection("memory://") as initial:
            consumer.ensure_connected(initial)
    consumer.app.conf.update(
        broker_connection_retry_on_startup=startup_retry,
        broker_connection_retry=runtime_retry,
    )
    with Connection(f"{unavailable_broker};memory://", connect_timeout=0.1) as broker:
        assert consumer.ensure_connected(broker) is broker
        assert broker.connected
        assert broker.transport.driver_type == "memory"
    assert connection_attempts(caplog) == 1


def test_worker_shutdown_interrupts_backoff_before_another_attempt(
    unavailable_broker: str, tmp_path: Path
) -> None:
    environment: dict[str, str] = os.environ.copy()
    environment.pop("DJANGO_SETTINGS_MODULE", None)
    environment["PYTHONUNBUFFERED"] = "1"
    environment["CELERY_BROKER_URL"] = unavailable_broker
    environment["CELERY_BROKER_READ_URL"] = unavailable_broker
    environment["CELERY_BROKER_WRITE_URL"] = unavailable_broker
    script: str = dedent(
        """
        import sys
        from celery import Celery

        application = Celery("shutdown-test", broker=sys.argv[1], fixups=[])
        application.conf.update(
            worker_consumer=(
                "speleodb.background_jobs.consumer:ExponentialBackoffConsumer"
            ),
            broker_connection_max_retries=5,
            broker_retry_base_delay_seconds=30.0,
            broker_retry_max_delay_seconds=30.0,
        )
        application.worker_main([
            "worker", "--pool=solo", "--concurrency=1", "--loglevel=INFO",
            "--without-gossip", "--without-mingle", "--without-heartbeat",
        ])
        """
    )
    log_path: Path = tmp_path / "worker.log"
    with log_path.open("w") as log:
        process: subprocess.Popen[str] = subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", script, unavailable_broker],
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            deadline: float = time.monotonic() + STARTUP_TIMEOUT_SECONDS
            while "Broker connection attempt 1/6 failed" not in log_path.read_text():
                assert process.poll() is None, log_path.read_text()
                assert time.monotonic() < deadline, log_path.read_text()
                time.sleep(0.05)
            process.terminate()
            assert process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS) == 0
            assert "attempt 2/6" not in log_path.read_text()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)


def test_non_connection_failure_is_not_retried(
    consumer: ExponentialBackoffConsumer,
    unavailable_broker: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    invalid_database: str = unavailable_broker.removesuffix("/0") + "/invalid"
    with (
        Connection(invalid_database, connect_timeout=0.1) as broker,
        pytest.raises(ValueError, match="Database is int"),
    ):
        consumer.ensure_connected(broker)
    assert connection_attempts(caplog) == 0


@pytest.mark.parametrize("max_retries", [None, -1, True])
def test_unbounded_or_invalid_broker_budget_is_rejected(
    consumer: ExponentialBackoffConsumer,
    max_retries: int | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    consumer.app.conf.update(broker_connection_max_retries=max_retries)
    with Connection("memory://") as broker:
        with pytest.raises(ValueError, match="finite nonnegative integer"):
            consumer.ensure_connected(broker)
        assert not broker.connected
    assert connection_attempts(caplog) == 0


def test_broker_backoff_is_capped(
    consumer: ExponentialBackoffConsumer,
    unavailable_broker: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    consumer.app.conf.update(broker_retry_max_delay_seconds=0.03)
    with (
        Connection(unavailable_broker, connect_timeout=0.1) as broker,
        caplog.at_level("DEBUG"),
        pytest.raises(OperationalError),
    ):
        consumer.ensure_connected(broker)
    assert retry_delays(caplog) == [0.01, 0.02, 0.03, 0.03, 0.03]


def test_broker_retry_logs_redact_connection_credentials(
    consumer: ExponentialBackoffConsumer,
    unavailable_broker: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    credential_url: str = unavailable_broker.replace(
        "redis://", "redis://:test-only-redaction-token@"
    )
    consumer.app.conf.update(broker_connection_max_retries=0)
    with (
        Connection(credential_url, connect_timeout=0.1) as broker,
        caplog.at_level("DEBUG"),
        pytest.raises(OperationalError),
    ):
        consumer.ensure_connected(broker)
    assert "test-only-redaction-token" not in caplog.text
    assert "OperationalError" in caplog.text
    assert ":**@" in caplog.text
