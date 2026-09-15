"""Exercise scheduler handover using independent real PostgreSQL sessions."""

from __future__ import annotations

import signal
import subprocess
import time
from threading import Event
from threading import Timer
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

import psycopg
import pytest
from django.core.management.base import CommandError
from django.db import connection

from speleodb.background_jobs.management.commands.run_background_beat import (
    BEAT_LOCK_ID,
)
from speleodb.background_jobs.management.commands.run_background_beat import (
    KILL_TIMEOUT_SECONDS,
)
from speleodb.background_jobs.management.commands.run_background_beat import (
    LOCK_WAIT_SECONDS,
)
from speleodb.background_jobs.management.commands.run_background_beat import (
    SHUTDOWN_TIMEOUT_SECONDS,
)
from speleodb.background_jobs.management.commands.run_background_beat import Command
from speleodb.background_jobs.management.commands.run_background_beat import (
    wait_for_scheduler_lock,
)

pytestmark = pytest.mark.django_db(transaction=True)


def competing_scheduler() -> psycopg.Connection[Any]:
    if connection.vendor != "postgresql":
        pytest.skip("Scheduler handover requires the PostgreSQL integration database.")
    parameters: dict[str, Any] = connection.get_connection_params()
    parameters["autocommit"] = True
    competing: psycopg.Connection[Any] = psycopg.connect(**parameters)
    competing.execute("SELECT pg_advisory_lock(%s)", [BEAT_LOCK_ID])
    return competing


def test_standby_acquires_lock_after_previous_scheduler_exits() -> None:
    competing: psycopg.Connection[Any] = competing_scheduler()
    stop_requested: Event = Event()
    release: Timer = Timer(0.1, competing.close)
    release.start()
    try:
        assert wait_for_scheduler_lock(stop_requested)
        assert competing.closed
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [BEAT_LOCK_ID])
            assert cursor.fetchone()[0]
    finally:
        release.join()
        competing.close()


def test_standby_stop_interrupts_lock_wait() -> None:
    competing: psycopg.Connection[Any] = competing_scheduler()
    stop_requested: Event = Event()
    stop: Timer = Timer(0.1, stop_requested.set)
    started: float = time.monotonic()
    stop.start()
    try:
        assert not wait_for_scheduler_lock(stop_requested)
        assert time.monotonic() - started < LOCK_WAIT_SECONDS
        assert not competing.closed
    finally:
        stop.join()
        competing.close()


def test_standby_exhausts_finite_lock_attempts_with_exponential_waits() -> None:
    stop_requested: Event = Event()
    with (
        patch(
            "speleodb.background_jobs.management.commands.run_background_beat.connection"
        ) as database,
        patch(
            "speleodb.background_jobs.management.commands.run_background_beat.LOCK_MAX_ATTEMPTS",
            3,
        ),
        patch.object(stop_requested, "wait", return_value=False) as wait,
    ):
        cursor: MagicMock = database.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (False,)
        with pytest.raises(CommandError, match="after 3 attempts"):
            wait_for_scheduler_lock(stop_requested)

    assert cursor.execute.call_count == 3  # noqa: PLR2004
    assert wait.call_args_list == [call(LOCK_WAIT_SECONDS), call(2 * LOCK_WAIT_SECONDS)]


def test_standby_stop_interrupts_exponential_backoff() -> None:
    stop_requested: Event = Event()
    with (
        patch(
            "speleodb.background_jobs.management.commands.run_background_beat.connection"
        ) as database,
        patch.object(stop_requested, "wait", side_effect=[False, True]) as wait,
    ):
        cursor: MagicMock = database.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (False,)
        assert not wait_for_scheduler_lock(stop_requested)

    assert cursor.execute.call_count == 2  # noqa: PLR2004
    assert wait.call_args_list == [call(LOCK_WAIT_SECONDS), call(2 * LOCK_WAIT_SECONDS)]


def test_stopped_standby_does_not_query_database() -> None:
    stop_requested: Event = Event()
    stop_requested.set()
    with patch(
        "speleodb.background_jobs.management.commands.run_background_beat.connection"
    ) as database:
        assert not wait_for_scheduler_lock(stop_requested)

    database.cursor.assert_not_called()


def test_shutdown_timeout_restores_handlers_and_closes_lock_connection() -> None:
    with (
        patch(
            "speleodb.background_jobs.management.commands.run_background_beat.connection"
        ) as database,
        patch(
            "speleodb.background_jobs.management.commands.run_background_beat.wait_for_scheduler_lock",
            return_value=True,
        ),
        patch(
            "speleodb.background_jobs.management.commands.run_background_beat.subprocess.Popen"
        ) as popen,
        patch(
            "speleodb.background_jobs.management.commands.run_background_beat.signal.signal",
            side_effect=[signal.SIG_DFL, signal.SIG_IGN, None, None],
        ) as signal_handler,
    ):
        database.vendor = "postgresql"
        database.is_usable.return_value = False
        process: MagicMock = popen.return_value
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired("celery beat", 5)

        with pytest.raises(CommandError, match="did not exit after being killed"):
            Command().handle()

    assert process.wait.call_args_list == [
        call(timeout=5),
        call(timeout=SHUTDOWN_TIMEOUT_SECONDS),
        call(timeout=KILL_TIMEOUT_SECONDS),
    ]
    process.terminate.assert_called_once_with()
    process.kill.assert_called_once_with()
    assert signal_handler.call_args_list[-2:] == [
        call(signal.SIGTERM, signal.SIG_DFL),
        call(signal.SIGINT, signal.SIG_IGN),
    ]
    database.close.assert_called_once_with()


def test_stop_request_leaves_supervision_when_beat_ignores_termination() -> None:
    stop_requested: Event = Event()

    def wait(*, timeout: int) -> int:
        if not stop_requested.is_set():
            stop_requested.set()
            raise subprocess.TimeoutExpired("celery beat", timeout)
        # Fail immediately if normal supervision resumes after the stop request.
        assert timeout == SHUTDOWN_TIMEOUT_SECONDS
        return 0

    with (
        patch(
            "speleodb.background_jobs.management.commands.run_background_beat.connection"
        ) as database,
        patch(
            "speleodb.background_jobs.management.commands.run_background_beat.Event",
            return_value=stop_requested,
        ),
        patch(
            "speleodb.background_jobs.management.commands.run_background_beat.wait_for_scheduler_lock",
            return_value=True,
        ),
        patch(
            "speleodb.background_jobs.management.commands.run_background_beat.subprocess.Popen"
        ) as popen,
        patch(
            "speleodb.background_jobs.management.commands.run_background_beat.signal.signal"
        ),
    ):
        database.vendor = "postgresql"
        database.is_usable.return_value = True
        process: MagicMock = popen.return_value
        process.poll.return_value = None
        process.wait.side_effect = wait
        process.returncode = 0

        Command().handle()

    assert process.wait.call_args_list == [
        call(timeout=5),
        call(timeout=SHUTDOWN_TIMEOUT_SECONDS),
    ]
    process.terminate.assert_called_once_with()
    process.kill.assert_not_called()
    database.close.assert_called_once_with()
