"""Exercise the pinned result backend against Django's actual test database."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from celery import Celery
from celery import states
from celery.app.task import Context
from django.utils import timezone
from django_celery_results.backends.database import DatabaseBackend
from django_celery_results.models import TaskResult

from config.celery_app import app

if TYPE_CHECKING:
    from collections.abc import Mapping


@pytest.mark.django_db
def test_django_result_backend_persists_json_execution_states() -> None:
    backend: DatabaseBackend = DatabaseBackend(app=app)
    task_id: str = str(uuid4())
    request: Context = Context(
        id=task_id,
        task="speleodb.users.tasks.get_users_count",
        args=[],
        kwargs={},
        hostname="result-history-test@worker",
        periodic_task_name="scheduled-user-count",
    )
    backend.store_result(
        task_id, {"stage": "uploading"}, states.STARTED, request=request
    )
    started: Mapping[str, object] = TaskResult.objects.values(
        "id", "status", "date_started"
    ).get(task_id=task_id)
    assert started["status"] == states.STARTED
    assert started["date_started"] is not None

    backend.store_result(
        task_id, {"outcome": "ready", "files": 5}, states.SUCCESS, request=request
    )
    assert backend.get_task_meta(task_id)["result"] == {
        "outcome": "ready",
        "files": 5,
    }
    record: TaskResult = TaskResult.objects.get(task_id=task_id)
    metadata: Mapping[str, object] = TaskResult.objects.values(
        "date_started", "worker", "periodic_task_name"
    ).get(task_id=task_id)
    assert record.status == states.SUCCESS
    assert record.content_type == "application/json"
    assert record.task_name == "speleodb.users.tasks.get_users_count"
    assert metadata["worker"] == "result-history-test@worker"
    assert metadata["periodic_task_name"] == "scheduled-user-count"
    assert record.task_args == "[]"
    assert record.task_kwargs == "{}"
    assert metadata["date_started"] == started["date_started"]
    assert record.pk == started["id"]
    assert TaskResult.objects.filter(task_id=task_id).count() == 1


@pytest.mark.parametrize(
    ("task_name", "ignore_result"),
    [
        ("speleodb.gis.tasks.dispatch_project_geojsons", True),
        ("speleodb.background_jobs.tasks.maintain_background_jobs", True),
        ("speleodb.background_jobs.tasks.delete_expired_artifacts", True),
        ("celery.backend_cleanup", True),
        ("speleodb.users.tasks.get_users_count", False),
    ],
)
def test_registered_task_publication_applies_result_history_policy(
    task_name: str, ignore_result: bool
) -> None:
    queue_name: str = f"result-policy-{uuid4().hex}"
    with Celery(queue_name, set_as_current=False) as publisher:
        publisher.config_from_object("django.conf:settings", namespace="CELERY")
        publisher.conf.update(
            broker_url="memory://",
            broker_read_url="memory://",
            broker_write_url="memory://",
            task_always_eager=False,
        )
        publisher.autodiscover_tasks(force=True)
        task = publisher.tasks[task_name]
        result = task.apply_async(queue=queue_name)
        with (
            publisher.connection_for_read() as broker,
            broker.SimpleQueue(queue_name) as queue,
        ):
            message = queue.get(block=False)
            assert message.headers["task"] == task_name
            assert message.headers["id"] == result.id
            # Kombu's headers stub permits strings, but Celery sends booleans.
            received_ignore_result: object = message.headers["ignore_result"]
            assert received_ignore_result is ignore_result
            message.ack()
        assert task.ignore_result is ignore_result
        if ignore_result:
            assert task.store_errors_even_if_ignored is True


@pytest.mark.django_db
def test_django_result_backend_cleanup_preserves_recent_results() -> None:
    backend: DatabaseBackend = DatabaseBackend(app=app, expires=timedelta(days=30))
    expired_id: str = str(uuid4())
    recent_id: str = str(uuid4())
    backend.store_result(expired_id, {}, states.SUCCESS)
    backend.store_result(recent_id, {}, states.SUCCESS)
    TaskResult.objects.filter(task_id=expired_id).update(
        date_done=timezone.now() - timedelta(days=31)
    )

    backend.cleanup()

    assert not TaskResult.objects.filter(task_id=expired_id).exists()
    assert TaskResult.objects.filter(task_id=recent_id).exists()
