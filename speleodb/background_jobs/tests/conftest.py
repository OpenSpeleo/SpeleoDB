"""Isolated task publication through Celery's actual in-process transport."""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING

import pytest
from celery import Celery
from celery._state import get_current_app

if TYPE_CHECKING:
    from collections.abc import Generator

    from kombu.simple import SimpleQueue


@pytest.fixture
def operation_queue() -> Generator[SimpleQueue]:
    previous = get_current_app()
    # Publish real Celery messages without dispatching test projects to the
    # development worker. Failed publication uses a real unavailable broker.
    with Celery("operation-publication-tests") as app:
        app.config_from_object("django.conf:settings", namespace="CELERY")
        app.conf.update(
            broker_url="memory://",
            broker_read_url="memory://",
            broker_write_url="memory://",
            task_always_eager=False,
        )
        try:
            with (
                app.connection_for_write() as connection,
                connection.SimpleQueue("background_control") as queue,
            ):
                queue.clear()
                try:
                    yield queue
                finally:
                    queue.clear()
        finally:
            previous.set_current()


@pytest.fixture
def unavailable_publication() -> Generator[None]:
    """Exercise real connection refusals without stopping a shared broker."""
    previous = get_current_app()
    with socket.socket() as reserved, Celery("unavailable-publication-tests") as app:
        reserved.bind(("127.0.0.1", 0))
        broker_url = f"redis://127.0.0.1:{reserved.getsockname()[1]}/0"
        app.config_from_object("django.conf:settings", namespace="CELERY")
        app.conf.update(
            broker_url=broker_url,
            broker_read_url=broker_url,
            broker_write_url=broker_url,
            broker_connection_timeout=1,
            broker_connection_max_retries=0,
            broker_transport_options={
                "socket_connect_timeout": 1,
                "socket_timeout": 1,
                "max_retries": 0,
            },
            task_always_eager=False,
            task_publish_retry=False,
        )
        try:
            yield
        finally:
            previous.set_current()
