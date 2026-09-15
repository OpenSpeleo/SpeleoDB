"""Keep one database scheduler active, including during deployment overlap."""

from __future__ import annotations

import signal
import subprocess
import sys
from threading import Event
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import connection

BEAT_LOCK_ID: int = 736735226
LOCK_WAIT_SECONDS: int = 5
LOCK_MAX_ATTEMPTS: int = 6
SHUTDOWN_TIMEOUT_SECONDS: int = 10
KILL_TIMEOUT_SECONDS: int = 5


def wait_for_scheduler_lock(stop_requested: Event) -> bool:
    """Wait for deployment handover with finite attempts and interruptible backoff."""
    for attempt in range(LOCK_MAX_ATTEMPTS):
        if stop_requested.is_set():
            return False
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", [BEAT_LOCK_ID])
            if cursor.fetchone()[0]:
                return True
        if attempt + 1 < LOCK_MAX_ATTEMPTS and stop_requested.wait(
            LOCK_WAIT_SECONDS * (2**attempt)
        ):
            return False
    raise CommandError(
        "Could not acquire the background scheduler lock after "
        f"{LOCK_MAX_ATTEMPTS} attempts."
    )


class Command(BaseCommand):
    help = "Run Celery Beat while holding the PostgreSQL scheduler lock."

    def handle(self, *args: Any, **options: Any) -> None:
        if connection.vendor != "postgresql":
            raise CommandError("The background scheduler requires PostgreSQL.")
        stop_requested: Event = Event()
        process: subprocess.Popen[bytes] | None = None

        def stop(signum: int, frame: Any) -> None:
            stop_requested.set()
            if process is not None and process.poll() is None:
                process.terminate()

        previous_term = signal.signal(signal.SIGTERM, stop)
        previous_int = signal.signal(signal.SIGINT, stop)
        try:
            self.stdout.write("Waiting for the background scheduler lock.")
            if not wait_for_scheduler_lock(stop_requested) or stop_requested.is_set():
                return
            # Keep this exact connection alive. Reconnecting could lose ownership
            # while an old scheduler continued publishing periodic work.
            owner_connection = connection.connection
            # The scheduler class comes from trusted application settings.
            process = subprocess.Popen(  # noqa: S603
                [
                    sys.executable,
                    "-m",
                    "celery",
                    "-A",
                    "config.celery_app",
                    "beat",
                    "--loglevel=INFO",
                    f"--scheduler={settings.CELERY_BEAT_SCHEDULER}",
                    "--pidfile=",
                ]
            )
            while not stop_requested.is_set() and process.poll() is None:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if (
                        connection.connection is not owner_connection
                        or not connection.is_usable()
                    ):
                        raise CommandError(
                            "Scheduler lock connection was lost."
                        ) from None
            if process.returncode and not stop_requested.is_set():
                raise CommandError(
                    f"Celery Beat exited with status {process.returncode}."
                )
        finally:
            try:
                if process is not None:
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        try:
                            process.wait(timeout=KILL_TIMEOUT_SECONDS)
                        except subprocess.TimeoutExpired as error:
                            raise CommandError(
                                "Celery Beat did not exit after being killed."
                            ) from error
            finally:
                try:
                    signal.signal(signal.SIGTERM, previous_term)
                    signal.signal(signal.SIGINT, previous_int)
                finally:
                    connection.close()
