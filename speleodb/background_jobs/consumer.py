"""Finite exponential broker retries through Celery's consumer extension point."""

from __future__ import annotations

import logging
import math
import time
from functools import partial
from typing import TYPE_CHECKING
from typing import override

from celery.worker.consumer import Consumer
from celery.worker.state import maybe_shutdown
from kombu.exceptions import OperationalError

from speleodb.utils.helpers import retry_with_backoff

if TYPE_CHECKING:
    from collections.abc import Callable

    from kombu import Connection

logger = logging.getLogger(__name__)


def _sleep_before_retry(
    delay: float, *, check_shutdown: Callable[[], None] | None = None
) -> None:
    """Keep Celery's shutdown checks responsive during an exponential delay."""
    if check_shutdown is None:
        time.sleep(delay)
        return
    remaining: float = delay
    for _ in range(math.ceil(delay)):
        check_shutdown()
        interval: float = min(1.0, remaining)
        time.sleep(interval)
        remaining -= interval
    check_shutdown()


def connect_with_backoff(
    conn: Connection,
    *,
    max_retries: int,
    base_delay: float,
    max_delay: float,
    check_shutdown: Callable[[], None] | None = None,
    on_retry: Callable[[int], None] | None = None,
) -> Connection:
    """Share one finite retry budget between worker and database scheduler."""
    if (
        isinstance(max_retries, bool)
        or not isinstance(max_retries, int)
        or max_retries < 0
    ):
        raise ValueError("Broker max retries must be a finite nonnegative integer")
    attempts: int = 0

    def connect_once() -> Connection:
        nonlocal attempts
        if check_shutdown is not None:
            check_shutdown()
        attempts += 1
        try:
            # Each SDK call gets exactly one attempt. Otherwise its own linear
            # retries would multiply this operation's retry budget.
            return conn.ensure_connection(max_retries=0, callback=check_shutdown)
        except OperationalError as error:
            logger.warning(
                "Broker connection attempt %d/%d failed for %s: %s",
                attempts,
                max_retries + 1,
                conn.as_uri(),
                type(error).__name__,
            )
            if attempts <= max_retries:
                if on_retry is not None:
                    on_retry(attempts)
                conn.maybe_switch_next()
            raise

    return retry_with_backoff(
        connect_once,
        retries=max_retries + 1,
        exc_types=(OperationalError,),
        base_delay=base_delay,
        max_delay=max_delay,
        sleep_fn=partial(_sleep_before_retry, check_shutdown=check_shutdown),
        log_error_details=False,
    )


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
            conn.connect()
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
