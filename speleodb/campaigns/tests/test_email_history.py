from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import pytest
from django.utils import timezone
from django_celery_results.models import TaskResult

from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationCampaignEmail
from speleodb.campaigns.models import email_template_choices
from speleodb.campaigns.operations import TASK_NAME
from speleodb.campaigns.operations import review_digest
from speleodb.campaigns.operations import schedule_campaign
from speleodb.campaigns.operations import snapshot
from speleodb.campaigns.tasks import send_campaign_email
from speleodb.common.enums import TaskResultStatus
from speleodb.users.tests.factories import UserFactory


@pytest.fixture
def history_campaign() -> DonationCampaign:
    today = timezone.localdate()
    return DonationCampaign.objects.create(
        email_main_subject="Main community appeal",
        email_main_template=email_template_choices()[0][0],
        email_reminder_subject="Before our campaign closes",
        reminder_email_template=email_template_choices()[0][0],
        donation_url="https://example.com/give",
        goal_usd=5000,
        start_date=today,
        end_date=today,
    )


@pytest.mark.django_db
@pytest.mark.parametrize("reminder", [False, True])
def test_real_batch_history_records_only_accepted_recipients(
    history_campaign: DonationCampaign, reminder: bool, mailoutbox: Any
) -> None:
    group_id = uuid4()
    content = snapshot(history_campaign, reminder=reminder)
    recipients = [UserFactory.create(), UserFactory.create(), UserFactory.create()]
    failed_recipient = recipients.pop()
    for recipient in [*recipients, failed_recipient]:
        recipient_content = {**content}
        if recipient == failed_recipient:
            recipient_content["subject"] = "Invalid\nHeader"
        task_id = str(uuid4())
        args = [
            recipient_content,
            recipient.email,
            "https://example.com/",
            str(recipient.pk),
        ]
        TaskResult.objects.create(
            task_id=task_id,
            task_name=TASK_NAME,
            status=TaskResultStatus.PENDING,
            task_args=json.dumps(args),
            meta=json.dumps(
                {
                    "operation": "campaign",
                    "time_limit": 120,
                    "is_test": False,
                    "campaign_id": str(history_campaign.pk),
                    "group_id": str(group_id),
                }
            ),
        )
        send_campaign_email.apply(args=tuple(args), task_id=task_id, throw=False)
    record = DonationCampaignEmail.objects.get()
    assert record.pk == group_id
    assert record.email_type == (
        DonationCampaignEmail.EmailType.REMINDER
        if reminder
        else DonationCampaignEmail.EmailType.MAIN
    )
    assert record.subject == content["subject"]
    assert record.template == content["template"]
    assert record.recipients == [recipient.email for recipient in recipients]
    assert [mail.to for mail in mailoutbox] == [
        [recipient.email] for recipient in recipients
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("scenario", ["preview", "failed", "donated-after-queue"])
def test_preview_failed_and_newly_donating_recipients_do_not_enter_real_send_history(
    history_campaign: DonationCampaign, scenario: str, mailoutbox: Any
) -> None:
    recipient = UserFactory.create()
    content = snapshot(history_campaign)
    if scenario == "failed":
        content["subject"] = "Invalid\nHeader"
    is_test = scenario == "preview"
    task_id = str(uuid4())
    args = [
        content,
        recipient.email,
        "https://example.com/",
        None if is_test else str(recipient.pk),
    ]
    task = TaskResult.objects.create(
        task_id=task_id,
        task_name=TASK_NAME,
        status=TaskResultStatus.PENDING,
        task_args=json.dumps(args),
        meta=json.dumps(
            {
                "operation": "campaign",
                "time_limit": 120,
                "is_test": is_test,
                "campaign_id": str(history_campaign.pk),
                "group_id": str(uuid4()),
            }
        ),
    )
    if scenario == "donated-after-queue":
        history_campaign.donors = [recipient.email.upper()]
        history_campaign.save(update_fields=["donors"])
    result = send_campaign_email.apply(args=tuple(args), task_id=task_id, throw=False)
    task.refresh_from_db()
    assert not DonationCampaignEmail.objects.exists()
    if scenario == "failed":
        assert task.status == TaskResultStatus.FAILURE
        assert isinstance(result.result, ValueError)
        assert not mailoutbox
    elif scenario == "donated-after-queue":
        assert task.status == TaskResultStatus.SUCCESS
        assert json.loads(task.result)["outcome"] == "skipped"
        assert not mailoutbox
    else:
        assert task.status == TaskResultStatus.SUCCESS
        assert [message.to for message in mailoutbox] == [[recipient.email]]


@pytest.mark.django_db
@pytest.mark.parametrize("reminder", [False, True])
def test_preview_and_live_campaign_content_match(
    history_campaign: DonationCampaign, reminder: bool, mailoutbox: Any
) -> None:
    operator = UserFactory.create(is_superuser=True)
    history_campaign.email_main_subject = "[Community] A preview of our impact!"
    history_campaign.email_reminder_subject = "[Reminder] Thank you — join us!"
    history_campaign.save()
    for is_test in (True, False):
        receipt = schedule_campaign(
            str(history_campaign.pk),
            requester=operator,
            site_url="https://example.com/",
            reminder=reminder,
            test_emails=[operator.email] if is_test else None,
            send_id=None if is_test else str(uuid4()),
            digest=None
            if is_test
            else review_digest(history_campaign, reminder=reminder),
        )
        for row in TaskResult.objects.filter(task_id__in=receipt.task_ids):
            send_campaign_email.apply(
                args=json.loads(row.task_args), task_id=row.task_id, throw=True
            )
        assert DonationCampaignEmail.objects.count() == (0 if is_test else 1)
    preview, live = mailoutbox
    expected = (
        history_campaign.email_reminder_subject
        if reminder
        else history_campaign.email_main_subject
    )
    assert preview.subject == live.subject == expected
    assert preview.body == live.body
    assert preview.alternatives == live.alternatives
