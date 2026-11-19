"""Campaign retries rebuild current content and retain task/recipient identity."""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any
from uuid import uuid4

import pytest
from celery import current_app
from celery.utils.saferepr import saferepr
from django.urls import reverse
from django.utils import timezone
from django_celery_results.models import TaskResult

from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import email_template_choices
from speleodb.campaigns.operations import TASK_NAME
from speleodb.campaigns.operations import snapshot
from speleodb.campaigns.tasks import send_campaign_email
from speleodb.common.enums import TaskResultStatus
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client
    from kombu.simple import SimpleQueue
    from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks

    from speleodb.users.models import User


def _failed_campaign(
    recipient_kind: str,
    *,
    reminder: bool = False,
    truncate_arguments: bool = True,
) -> tuple[TaskResult, DonationCampaign, User | None]:
    current_app.conf.update(task_store_eager_result=True)
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        email_main_template=email_template_choices()[0][0],
        email_main_subject="Invalid\nsubject",
        reminder_email_template=email_template_choices()[0][0] if reminder else "",
        email_reminder_subject="Invalid\nreminder" if reminder else "",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today,
        end_date=today,
    )
    user = None if recipient_kind == "email" else UserFactory.create()
    email = user.email if user else "explicit@example.test"
    metadata: dict[str, Any] = {
        "operation": "campaign",
        "campaign_id": str(campaign.pk),
        "group_id": str(uuid4()),
        "is_test": user is None,
        "is_reminder": reminder,
        "project_users_only": False,
        "recipient": email,
        "time_limit": 120,
    }
    if recipient_kind != "legacy_user":
        metadata["user_id"] = str(user.pk) if user else None
        metadata["site_url"] = "https://campaign.example.test/"
    args = (
        snapshot(campaign, reminder=reminder),
        email,
        "https://campaign.example.test/",
        str(user.pk) if user else None,
    )
    result = TaskResult.objects.create(
        task_id=str(uuid4()),
        task_name=TASK_NAME,
        status=TaskResultStatus.PENDING,
        task_args=json.dumps(args),
        task_kwargs="{}",
        content_type="application/json",
        content_encoding="utf-8",
        meta=json.dumps(metadata),
    )
    # The actual Django email backend rejects the newline in the subject.
    execution = send_campaign_email.apply(
        args=args, task_id=result.task_id, throw=False
    )
    assert execution.failed()
    result.refresh_from_db()
    assert result.status == TaskResultStatus.FAILURE
    if truncate_arguments:
        # Reproduce the actual representation stored for older broker deliveries.
        result.task_args = json.dumps(saferepr(args, maxlen=1024))
        result.save(update_fields=["task_args"])
    return result, campaign, user


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("recipient_kind", "reminder"),
    [("email", False), ("user", False), ("legacy_user", False), ("user", True)],
)
def test_campaign_retry_fetches_current_content_and_recipient(  # noqa: PLR0917 - Explicit pytest fixtures.
    admin_client: Client,
    operation_queue: SimpleQueue,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    mailoutbox: Any,
    recipient_kind: str,
    reminder: bool,
) -> None:
    result, campaign, user = _failed_campaign(recipient_kind, reminder=reminder)
    campaign.email_main_subject = "Updated campaign subject"
    if reminder:
        campaign.email_reminder_subject = "Updated reminder subject"
    campaign.goal_usd += 1
    campaign.save()
    if recipient_kind == "user":
        assert user is not None
        user.email = "updated@example.test"
        user.save(update_fields=["email"])
    expected_email = user.email if user else "explicit@example.test"
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(
            reverse("admin:django_celery_results_taskresult_changelist"),
            {"action": "retry_failed", "_selected_action": str(result.pk)},
        )
    assert response.status_code == HTTPStatus.FOUND
    assert TaskResult.objects.get().pk == result.pk
    result.refresh_from_db()
    assert result.status == TaskResultStatus.PENDING
    args = json.loads(result.task_args)
    assert args[0] == snapshot(campaign, reminder=reminder)
    assert args[1] == expected_email
    assert args[3] == (str(user.pk) if user else None)
    assert json.loads(result.meta)["recipient"] == expected_email
    assert json.loads(result.meta)["user_id"] == args[3]
    message = operation_queue.get(block=False)
    assert message.headers["id"] == result.task_id
    execution = send_campaign_email.apply(
        args=tuple(message.payload[0]),
        kwargs=message.payload[1],
        task_id=message.headers["id"],
        headers=message.headers,
        throw=False,
    )
    message.ack()
    assert execution.successful()
    result.refresh_from_db()
    assert result.status == TaskResultStatus.SUCCESS
    assert TaskResult.objects.count() == 1
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == [expected_email]
    assert mailoutbox[0].subject == args[0]["subject"]


@pytest.mark.django_db
def test_missing_linked_user_does_not_fall_back_to_the_old_email(
    admin_client: Client,
    operation_queue: SimpleQueue,
) -> None:
    result, _, user = _failed_campaign("user")
    assert user is not None
    user.delete()
    response = admin_client.post(
        reverse("admin:django_celery_results_taskresult_changelist"),
        {"action": "retry_failed", "_selected_action": str(result.pk)},
        follow=True,
    )
    assert "recipient user is unavailable" in response.content.decode()
    assert operation_queue.qsize() == 0
    result.refresh_from_db()
    assert result.status == TaskResultStatus.FAILURE


@pytest.mark.django_db
def test_intact_legacy_identity_survives_email_reassignment(
    admin_client: Client,
    operation_queue: SimpleQueue,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    result, campaign, user = _failed_campaign("legacy_user", truncate_arguments=False)
    assert user is not None
    original_email = user.email
    user.email = "current-recipient@example.test"
    user.save(update_fields=["email"])
    replacement = UserFactory.create(email=original_email)
    campaign.email_main_subject = "Corrected campaign subject"
    campaign.save(update_fields=["email_main_subject"])
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(
            reverse("admin:django_celery_results_taskresult_changelist"),
            {"action": "retry_failed", "_selected_action": str(result.pk)},
        )
    assert response.status_code == HTTPStatus.FOUND
    result.refresh_from_db()
    assert TaskResult.objects.get().pk == result.pk
    assert json.loads(result.meta)["user_id"] == str(user.pk)
    message = operation_queue.get(block=False)
    assert message.headers["id"] == result.task_id
    assert message.payload[0][1] == user.email
    assert message.payload[0][3] == str(user.pk)
    assert message.payload[0][3] != str(replacement.pk)
    message.ack()
