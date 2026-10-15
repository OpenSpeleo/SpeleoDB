"""Finite exponential broker retries through Celery's consumer extension point."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import override

from celery.worker.consumer import Consumer
from celery.worker.state import maybe_shutdown

from speleodb.background_jobs.broker import connect_with_backoff

if TYPE_CHECKING:
    from kombu import Connection


class ExponentialBackoffConsumer(Consumer):
    @override
    def ensure_connected(self, conn: Connection) -> Connection:
        startup_retry: bool | None = self.app.conf.broker_connection_retry_on_startup
        retry_enabled: bool = (
            startup_retry
            if self.first_connection_attempt and startup_retry is not None
            else self.app.conf.broker_connection_retry
        )
        maybe_shutdown()
        if not retry_enabled:
            # Kombu.connect() performs one retry of its own. Explicitly disable
            # that budget while preserving the transport's original exception.
            conn.ensure_connection(max_retries=0, reraise_as_library_errors=False)
            self.first_connection_attempt = False
            return conn

        def record_retry(attempt: int) -> None:
            self.broker_connection_retry_attempt = attempt

        connected: Connection = connect_with_backoff(
            conn,
            max_retries=self.app.conf.broker_connection_max_retries,
            base_delay=self.app.conf.broker_retry_base_delay_seconds,
            max_delay=self.app.conf.broker_retry_max_delay_seconds,
            check_shutdown=maybe_shutdown,
            on_retry=record_retry,
        )
        self.first_connection_attempt = False
        self.broker_connection_retry_attempt = 0
        return connected
