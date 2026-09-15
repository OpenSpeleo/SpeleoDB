from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import PropertyMock
from unittest.mock import patch

import pytest
from celery.exceptions import WorkerShutdown
from kombu import Connection
from kombu.exceptions import OperationalError

from speleodb.background_jobs.consumer import ExponentialBackoffConsumer
from speleodb.background_jobs.scheduler import ExponentialBackoffDatabaseScheduler


@pytest.fixture
def consumer() -> ExponentialBackoffConsumer:
    instance = object.__new__(ExponentialBackoffConsumer)
    instance.app = MagicMock()
    instance.app.conf.broker_connection_retry_on_startup = True
    instance.app.conf.broker_connection_retry = True
    instance.app.conf.broker_connection_max_retries = 5
    instance.app.conf.broker_retry_base_delay_seconds = 1.0
    instance.app.conf.broker_retry_max_delay_seconds = 30.0
    instance.first_connection_attempt = True
    instance.broker_connection_retry_attempt = 0
    return instance


def test_broker_retries_stop_at_budget_with_exponential_delays(
    consumer: ExponentialBackoffConsumer,
) -> None:
    conn = MagicMock(spec=Connection)
    failure = OperationalError("Connection refused")
    conn.ensure_connection.side_effect = failure
    with (
        patch("speleodb.background_jobs.consumer._sleep_before_retry") as sleep,
        pytest.raises(OperationalError) as error,
    ):
        consumer.ensure_connected(conn)

    assert error.value is failure
    assert conn.ensure_connection.call_count == 6  # noqa: PLR2004
    assert conn.maybe_switch_next.call_count == 5  # noqa: PLR2004
    assert [item.args[0] for item in sleep.call_args_list] == [1, 2, 4, 8, 16]
    assert all(
        item.kwargs["max_retries"] == 0
        for item in conn.ensure_connection.call_args_list
    )


def test_broker_success_resets_state_and_retains_failover(
    consumer: ExponentialBackoffConsumer,
) -> None:
    conn = MagicMock(spec=Connection)
    conn.ensure_connection.side_effect = [OperationalError("first broker down"), conn]
    with patch("speleodb.background_jobs.consumer._sleep_before_retry") as sleep:
        assert consumer.ensure_connected(conn) is conn

    conn.maybe_switch_next.assert_called_once_with()
    assert sleep.call_count == 1
    assert sleep.call_args.args == (1.0,)
    assert consumer.first_connection_attempt is False
    assert consumer.broker_connection_retry_attempt == 0


@pytest.mark.parametrize(
    ("first_connection", "startup_retry", "runtime_retry"),
    [(True, False, True), (False, True, False), (True, None, False)],
)
def test_disabled_retry_uses_single_direct_connect(
    consumer: ExponentialBackoffConsumer,
    first_connection: bool,
    startup_retry: bool | None,
    runtime_retry: bool,
) -> None:
    consumer.first_connection_attempt = first_connection
    consumer.app.conf.broker_connection_retry_on_startup = startup_retry
    consumer.app.conf.broker_connection_retry = runtime_retry
    conn = MagicMock(spec=Connection)

    with patch("speleodb.background_jobs.consumer._sleep_before_retry") as sleep:
        assert consumer.ensure_connected(conn) is conn

    conn.connect.assert_called_once_with()
    conn.ensure_connection.assert_not_called()
    sleep.assert_not_called()


@pytest.mark.parametrize(
    ("first_connection", "startup_retry", "runtime_retry"),
    [(True, True, False), (False, False, True), (True, None, True)],
)
def test_enabled_retry_respects_startup_and_runtime_flags(
    consumer: ExponentialBackoffConsumer,
    first_connection: bool,
    startup_retry: bool | None,
    runtime_retry: bool,
) -> None:
    consumer.first_connection_attempt = first_connection
    consumer.app.conf.broker_connection_retry_on_startup = startup_retry
    consumer.app.conf.broker_connection_retry = runtime_retry
    conn = MagicMock(spec=Connection)
    conn.ensure_connection.return_value = conn

    assert consumer.ensure_connected(conn) is conn

    conn.ensure_connection.assert_called_once()
    conn.connect.assert_not_called()


def test_worker_shutdown_interrupts_backoff_before_another_attempt(
    consumer: ExponentialBackoffConsumer,
) -> None:
    consumer.app.conf.broker_retry_base_delay_seconds = 4.0
    conn = MagicMock(spec=Connection)
    conn.ensure_connection.side_effect = OperationalError("broker unavailable")
    with (
        patch(
            "speleodb.background_jobs.consumer.maybe_shutdown",
            side_effect=[None, None, None, WorkerShutdown()],
        ),
        patch("speleodb.background_jobs.consumer.time.sleep") as sleep,
        pytest.raises(WorkerShutdown),
    ):
        consumer.ensure_connected(conn)

    conn.ensure_connection.assert_called_once()
    sleep.assert_called_once_with(1.0)


def test_non_connection_failure_is_not_retried(
    consumer: ExponentialBackoffConsumer,
) -> None:
    conn = MagicMock(spec=Connection)
    conn.ensure_connection.side_effect = ValueError("invalid broker configuration")
    with (
        patch("speleodb.background_jobs.consumer._sleep_before_retry") as sleep,
        pytest.raises(ValueError, match="invalid broker configuration"),
    ):
        consumer.ensure_connected(conn)

    conn.ensure_connection.assert_called_once()
    conn.maybe_switch_next.assert_not_called()
    sleep.assert_not_called()


@pytest.mark.parametrize("max_retries", [None, -1, True])
def test_unbounded_or_invalid_broker_budget_is_rejected(
    consumer: ExponentialBackoffConsumer, max_retries: int | None
) -> None:
    consumer.app.conf.broker_connection_max_retries = max_retries
    conn = MagicMock(spec=Connection)

    with pytest.raises(ValueError, match="finite nonnegative integer"):
        consumer.ensure_connected(conn)

    conn.ensure_connection.assert_not_called()


def test_broker_backoff_is_capped(consumer: ExponentialBackoffConsumer) -> None:
    consumer.app.conf.broker_retry_max_delay_seconds = 3.0
    conn = MagicMock(spec=Connection)
    conn.ensure_connection.side_effect = OperationalError("unavailable")
    with (
        patch("speleodb.background_jobs.consumer._sleep_before_retry") as sleep,
        pytest.raises(OperationalError),
    ):
        consumer.ensure_connected(conn)

    assert [item.args[0] for item in sleep.call_args_list] == [1, 2, 3, 3, 3]


def test_broker_retry_logs_do_not_include_raw_error_credentials(
    consumer: ExponentialBackoffConsumer, caplog: pytest.LogCaptureFixture
) -> None:
    conn = MagicMock(spec=Connection)
    conn.as_uri.return_value = "redis://:**@redis:6379/1"
    conn.ensure_connection.side_effect = OperationalError("secret-password")
    with (
        caplog.at_level("DEBUG"),
        patch("speleodb.background_jobs.consumer._sleep_before_retry"),
        pytest.raises(OperationalError),
    ):
        consumer.ensure_connected(conn)

    assert "secret-password" not in caplog.text
    assert "OperationalError" in caplog.text


def test_database_scheduler_uses_same_finite_exponential_budget(
    consumer: ExponentialBackoffConsumer,
) -> None:
    scheduler = object.__new__(ExponentialBackoffDatabaseScheduler)
    scheduler.app = consumer.app
    conn = MagicMock(spec=Connection)
    failure = OperationalError("broker down")
    conn.ensure_connection.side_effect = failure

    with (
        patch.object(
            ExponentialBackoffDatabaseScheduler,
            "connection",
            new_callable=PropertyMock,
            return_value=conn,
        ),
        patch("speleodb.background_jobs.consumer._sleep_before_retry") as sleep,
        pytest.raises(OperationalError) as error,
    ):
        scheduler._ensure_connected()  # noqa: SLF001

    assert error.value is failure
    assert conn.ensure_connection.call_count == 6  # noqa: PLR2004
    assert [item.args[0] for item in sleep.call_args_list] == [1, 2, 4, 8, 16]


def test_database_scheduler_connection_can_recover(
    consumer: ExponentialBackoffConsumer,
) -> None:
    scheduler = object.__new__(ExponentialBackoffDatabaseScheduler)
    scheduler.app = consumer.app
    conn = MagicMock(spec=Connection)
    conn.ensure_connection.side_effect = [OperationalError("temporary"), conn]

    with (
        patch.object(
            ExponentialBackoffDatabaseScheduler,
            "connection",
            new_callable=PropertyMock,
            return_value=conn,
        ),
        patch("speleodb.background_jobs.consumer._sleep_before_retry") as sleep,
    ):
        assert scheduler._ensure_connected() is conn  # noqa: SLF001

    conn.maybe_switch_next.assert_called_once()
    assert sleep.call_count == 1
    assert sleep.call_args.args == (1.0,)
