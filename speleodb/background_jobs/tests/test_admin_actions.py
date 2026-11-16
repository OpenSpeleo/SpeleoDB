"""Explicit administrator actions record their changes without execution noise."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from allauth.account.models import EmailAddress
from django.urls import reverse
from django.utils import timezone
from django_celery_beat.models import IntervalSchedule
from django_celery_beat.models import PeriodicTask
from rest_framework import status

from speleodb.api.v2.tests.factories import ExperimentFactory
from speleodb.users.models import LogEntry
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client
    from kombu.simple import SimpleQueue
    from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks

    from speleodb.users.models import User


@pytest.mark.django_db
def test_email_verification_action_audits_only_the_changed_address(
    admin_client: Client,
) -> None:
    user = UserFactory.create()
    address = EmailAddress.objects.create(user=user, email=user.email, verified=False)
    url = reverse("admin:account_emailaddress_changelist")
    payload = {"action": "make_verified", "_selected_action": [address.pk]}
    assert admin_client.post(url, payload).status_code == status.HTTP_302_FOUND
    address.refresh_from_db()
    assert address.verified
    entries = LogEntry.objects.filter(object_id=str(address.pk))
    assert entries.count() == 1
    assert "verified" in entries.get().get_change_message()
    assert admin_client.post(url, payload).status_code == status.HTTP_302_FOUND
    assert entries.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("edit_name", [False, True])
def test_experiment_token_rotation_is_in_the_single_change_message(
    admin_client: Client, admin_user: User, *, edit_name: bool
) -> None:
    experiment = ExperimentFactory.create(created_by=admin_user.email)
    previous_token = experiment.gis_token
    name = "Renamed experiment" if edit_name else experiment.name
    response = admin_client.post(
        reverse("admin:gis_experiment_change", args=[experiment.pk]),
        {
            "name": name,
            "code": experiment.code,
            "description": experiment.description,
            "is_active": "on",
            "_refresh_token": "Refresh Token",
        },
    )
    assert response.status_code == status.HTTP_302_FOUND
    experiment.refresh_from_db()
    assert experiment.gis_token != previous_token
    assert experiment.name == name
    entry = LogEntry.objects.get(object_id=str(experiment.pk))
    message = entry.get_change_message()
    assert "GIS token (refreshed)" in message
    assert previous_token not in message
    assert experiment.gis_token not in message
    if edit_name:
        assert "Name" in message or "name" in message


@pytest.mark.django_db
def test_schedule_actions_audit_state_changes_only(admin_client: Client) -> None:
    interval = IntervalSchedule.objects.create(
        every=60, period=IntervalSchedule.SECONDS
    )
    task = PeriodicTask.objects.create(
        name="Audited schedule",
        task="celery.backend_cleanup",
        interval=interval,
        enabled=False,
    )
    url = reverse("admin:django_celery_beat_periodictask_changelist")
    payload = {"action": "enable_tasks", "_selected_action": [task.pk]}
    assert admin_client.post(url, payload).status_code == status.HTTP_302_FOUND
    task.refresh_from_db()
    assert task.enabled
    entries = LogEntry.objects.filter(object_id=str(task.pk))
    assert entries.count() == 1
    assert "Enabled" in entries.get().get_change_message()
    assert admin_client.post(url, payload).status_code == status.HTTP_302_FOUND
    assert entries.count() == 1
    payload["action"] = "toggle_tasks"
    assert admin_client.post(url, payload).status_code == status.HTTP_302_FOUND
    task.refresh_from_db()
    assert not task.enabled
    expected_messages = ["Enabled scheduled task.", "Disabled scheduled task."]
    assert (
        list(entries.order_by("action_time").values_list("change_message", flat=True))
        == expected_messages
    )
    payload["action"] = "disable_tasks"
    assert admin_client.post(url, payload).status_code == status.HTTP_302_FOUND
    assert (
        list(entries.order_by("action_time").values_list("change_message", flat=True))
        == expected_messages
    )
    PeriodicTask.objects.filter(pk=task.pk).update(
        enabled=True, last_run_at=timezone.now()
    )
    assert admin_client.post(url, payload).status_code == status.HTTP_302_FOUND
    task.refresh_from_db()
    assert not task.enabled
    assert task.last_run_at is None
    expected_messages.append("Disabled scheduled task and cleared its last run.")
    assert (
        list(entries.order_by("action_time").values_list("change_message", flat=True))
        == expected_messages
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
def test_manual_schedule_run_records_one_request_for_selected_tasks(
    admin_client: Client,
    operation_queue: SimpleQueue,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    interval = IntervalSchedule.objects.create(
        every=60, period=IntervalSchedule.SECONDS
    )
    tasks = [
        PeriodicTask.objects.create(
            name=f"Manual schedule {number}",
            task="celery.backend_cleanup",
            interval=interval,
            queue="background_control",
        )
        for number in range(2)
    ]
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(
            reverse("admin:django_celery_beat_periodictask_changelist"),
            {"action": "run_tasks", "_selected_action": [task.pk for task in tasks]},
        )
        assert operation_queue.qsize() == 0
    assert response.status_code == status.HTTP_302_FOUND
    assert operation_queue.qsize() == len(tasks)
    assert LogEntry.objects.count() == 1
    entry = LogEntry.objects.get()
    assert entry.action_flag == LogEntry.Action.ACTION
    assert "Requested manual execution" in entry.get_change_message()
    received_ids: set[str] = set()
    for _ in tasks:
        message = operation_queue.get(block=False)
        received_ids.add(message.headers["id"])
        message.ack()
    assert set(entry.details["task_ids"]) == received_ids
    assert {target["id"] for target in entry.details["targets"]} == {
        str(task.pk) for task in tasks
    }


@pytest.mark.django_db
@pytest.mark.usefixtures("operation_queue")
def test_unknown_manual_schedule_does_not_record_or_publish_a_request(
    admin_client: Client, operation_queue: SimpleQueue
) -> None:
    interval = IntervalSchedule.objects.create(
        every=60, period=IntervalSchedule.SECONDS
    )
    task = PeriodicTask.objects.create(
        name="Unknown manual schedule",
        task="unknown.admin.audit.task",
        interval=interval,
    )
    response = admin_client.post(
        reverse("admin:django_celery_beat_periodictask_changelist"),
        {"action": "run_tasks", "_selected_action": [task.pk]},
    )
    assert response.status_code == status.HTTP_302_FOUND
    assert operation_queue.qsize() == 0
    assert not LogEntry.objects.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("unavailable_publication")
def test_manual_schedule_publication_failure_preserves_the_request(
    admin_client: Client,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    interval = IntervalSchedule.objects.create(
        every=60, period=IntervalSchedule.SECONDS
    )
    task = PeriodicTask.objects.create(
        name="Unavailable manual publication",
        task="celery.backend_cleanup",
        interval=interval,
        queue="background_control",
    )
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(
            reverse("admin:django_celery_beat_periodictask_changelist"),
            {"action": "run_tasks", "_selected_action": [task.pk]},
        )
    assert response.status_code == status.HTTP_302_FOUND
    entry = LogEntry.objects.get()
    assert entry.action_flag == LogEntry.Action.ACTION
    assert entry.details["targets"] == [
        {"id": str(task.pk), "name": task.name, "task": task.task}
    ]
    assert "Requested manual execution" in entry.get_change_message()
