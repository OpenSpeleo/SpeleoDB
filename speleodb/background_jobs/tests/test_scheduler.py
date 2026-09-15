"""Exercise scheduler handover using independent real PostgreSQL sessions."""

from __future__ import annotations

import time
from threading import Event
from threading import Timer
from typing import Any

import psycopg
import pytest
from django.db import connection

from speleodb.background_jobs.management.commands.run_background_beat import (
    BEAT_LOCK_ID,
)
from speleodb.background_jobs.management.commands.run_background_beat import (
    LOCK_WAIT_SECONDS,
)
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
