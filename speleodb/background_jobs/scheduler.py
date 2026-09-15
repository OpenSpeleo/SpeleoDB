"""Keep the database scheduler while bounding broker retries exponentially."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django_celery_beat.schedulers import DatabaseScheduler

from speleodb.background_jobs.consumer import connect_with_backoff

if TYPE_CHECKING:
    from kombu import Connection


class ExponentialBackoffDatabaseScheduler(DatabaseScheduler):
    # Celery's runtime hook is absent from the upstream scheduler type stubs.
    def _ensure_connected(self) -> Connection:
        return connect_with_backoff(
            self.connection,
            max_retries=self.app.conf.broker_connection_max_retries,
            base_delay=self.app.conf.broker_retry_base_delay_seconds,
            max_delay=self.app.conf.broker_retry_max_delay_seconds,
        )
