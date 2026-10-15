"""A dedicated synchronous PostgreSQL session tracks scheduler lock ownership."""

from __future__ import annotations

import time
from typing import Any

import psycopg

BEAT_LOCK_ID: int = 736735226
LOCK_WAIT_SECONDS: int = 5
LOCK_MAX_ATTEMPTS: int = 6
DATABASE_TIMEOUT_SECONDS: int = 5


class SchedulerLeaseLostError(RuntimeError):
    """Ownership is terminally lost; this process must never publish again."""


class SchedulerLease:
    def __init__(self, parameters: dict[str, Any]) -> None:
        self.parameters = parameters.copy()
        self.connection: psycopg.Connection[Any] | None = None
        self.active: bool = False
        self.lost: bool = False

    def acquire(self) -> None:
        if self.connection is not None or self.lost:
            raise RuntimeError("A scheduler lease cannot be reacquired.")
        self.parameters.update(
            autocommit=True,
            connect_timeout=DATABASE_TIMEOUT_SECONDS,
            keepalives=1,
            keepalives_idle=DATABASE_TIMEOUT_SECONDS,
            keepalives_interval=1,
            keepalives_count=DATABASE_TIMEOUT_SECONDS,
            tcp_user_timeout=DATABASE_TIMEOUT_SECONDS * 1000,
        )
        self.connection = psycopg.connect(**self.parameters)
        self.connection.execute(
            "SELECT set_config('statement_timeout', %s, false)",
            [str(DATABASE_TIMEOUT_SECONDS * 1000)],
        )
        for attempt in range(LOCK_MAX_ATTEMPTS):
            row: Any = self.connection.execute(
                "SELECT pg_try_advisory_lock(%s)", [BEAT_LOCK_ID]
            ).fetchone()
            if row and row[0]:
                self.active = True
                return
            if attempt + 1 < LOCK_MAX_ATTEMPTS:
                time.sleep(LOCK_WAIT_SECONDS * (2**attempt))
        raise RuntimeError(
            "Could not acquire the background scheduler lock after "
            f"{LOCK_MAX_ATTEMPTS} attempts."
        )

    def assert_owned(self) -> None:
        if not self.active or self.lost or self.connection is None:
            raise SchedulerLeaseLostError("Scheduler lock is no longer owned.")
        try:
            # Keep this exact connection alive. Reconnecting could lose ownership
            # while an old scheduler continued publishing periodic work.
            row: Any = self.connection.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE "
                "locktype = 'advisory' AND pid = pg_backend_pid() "
                "AND classid = %s AND objid = %s AND objsubid = 1 AND granted)",
                [BEAT_LOCK_ID >> 32, BEAT_LOCK_ID & 0xFFFFFFFF],
            ).fetchone()
            if row and row[0]:
                return
        except psycopg.Error as error:
            self.active = False
            self.lost = True
            raise SchedulerLeaseLostError(
                "Scheduler lock connection was lost."
            ) from error
        self.active = False
        self.lost = True
        raise SchedulerLeaseLostError("Scheduler lock is no longer owned.")

    def close(self) -> None:
        self.active = False
        if self.connection is not None:
            self.connection.close()
