"""Exercise the pinned result backend against Django's actual test database."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from celery import states
from django.utils import timezone
from django_celery_results.backends.database import DatabaseBackend
from django_celery_results.models import TaskResult

from config.celery_app import app


@pytest.mark.django_db
def test_django_result_backend_persists_json_execution_states() -> None:
    backend: DatabaseBackend = DatabaseBackend(app=app)
    task_id: str = str(uuid4())
    backend.store_result(task_id, {"stage": "uploading"}, states.STARTED)
    assert TaskResult.objects.get(task_id=task_id).status == states.STARTED

    backend.store_result(task_id, {"outcome": "ready", "files": 5}, states.SUCCESS)
    assert backend.get_task_meta(task_id)["result"] == {
        "outcome": "ready",
        "files": 5,
    }
    record: TaskResult = TaskResult.objects.get(task_id=task_id)
    assert record.status == states.SUCCESS
    assert record.content_type == "application/json"


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
