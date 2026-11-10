"""Check consumer validation and single-attempt broker failures."""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING

import pytest
from celery import Celery
from celery.result import denied_join_result
from celery.worker import WorkController
from django.conf import settings
from django.db import connections
from kombu import Connection
from kombu.exceptions import OperationalError

from speleodb.background_jobs.consumer import ExponentialBackoffConsumer

if TYPE_CHECKING:
    from collections.abc import Iterator


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
            broker_retry_base_delay_seconds=(
                settings.CELERY_BROKER_RETRY_BASE_DELAY_SECONDS
            ),
            broker_retry_max_delay_seconds=(
                settings.CELERY_BROKER_RETRY_MAX_DELAY_SECONDS
            ),
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


def connection_attempts(caplog: pytest.LogCaptureFixture) -> int:
    return sum(
        record.name == "speleodb.background_jobs.broker" for record in caplog.records
    )


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
