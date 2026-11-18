"""Reviewed campaign submissions and permanent launch protection."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import timedelta
from functools import partial
from typing import Any
from uuid import uuid4

from celery import current_app
from celery.result import GroupResult
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django_celery_results.models import TaskResult

from speleodb.background_jobs.operations import OperationReceipt
from speleodb.background_jobs.operations import _publish
from speleodb.campaigns.mail import CONTENT_FIELDS
from speleodb.campaigns.models import DonationCampaign
from speleodb.common.enums import TaskResultStatus
from speleodb.users.models import LogEntry
from speleodb.users.models import User

TASK_NAME = "speleodb.campaigns.tasks.send_campaign_email"


def audience() -> list[dict[str, str]]:
    recipients: dict[str, dict[str, str]] = {}
    for user in (
        User.objects.filter(email_on_speleodb_updates=True)
        .exclude(email="")
        .order_by("pk")
        .iterator()
    ):
        recipients.setdefault(
            user.email.casefold(), {"user_id": str(user.pk), "email": user.email}
        )
    return list(recipients.values())


def snapshot(campaign: DonationCampaign) -> dict[str, Any]:
    return {
        **{field: deepcopy(getattr(campaign, field)) for field in CONTENT_FIELDS},
        "photo_url": campaign.photo_url,
        "photo_name": campaign.photo.name,
        "formatted_goal": campaign.formatted_goal,
        "resolved_goal_message": campaign.resolved_goal_message,
        "resolved_card_summary": campaign.resolved_card_summary,
        "resolved_recipient_notice": campaign.resolved_recipient_notice,
    }


def review_digest(campaign: DonationCampaign) -> str:
    data = {
        "content": snapshot(campaign),
        "audience": audience(),
        "modified": campaign.modified_date.isoformat(),
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def schedule_campaign(
    campaign_id: str,
    *,
    requester: User,
    site_url: str,
    digest: str | None = None,
    test_emails: list[str] | None = None,
) -> OperationReceipt:
    if not requester.is_active or not requester.is_superuser:
        raise PermissionDenied
    group_id = str(uuid4())
    with transaction.atomic():
        campaign = DonationCampaign.objects.select_for_update().get(pk=campaign_id)
        content = snapshot(campaign)
        recipients: list[dict[str, Any]]
        if test_emails is None:
            if campaign.launched_at is not None:
                raise ValueError(
                    "This campaign has already been submitted. "
                    "Inspect its task results before any resend."
                )
            if digest != review_digest(campaign):
                raise ValueError("Campaign content or audience changed. Review again.")
            recipients = audience()
            if not recipients:
                raise ValueError("No eligible recipients.")
            campaign.launched_at = timezone.now()
            campaign.approved_snapshot = {**content, "group_id": group_id}
            campaign.save(
                update_fields=["launched_at", "approved_snapshot", "modified_date"]
            )
        else:
            if not test_emails:
                raise ValueError("Enter at least one test address.")
            recipients = [
                {"user_id": None, "email": email}
                for email in dict.fromkeys(test_emails)
            ]
        task_ids = []
        for recipient in recipients:
            task_id = str(uuid4())
            TaskResult.objects.create(
                task_id=task_id,
                task_name=TASK_NAME,
                status=TaskResultStatus.PENDING,
                task_args=json.dumps(
                    [content, recipient["email"], site_url, recipient["user_id"]]
                ),
                task_kwargs="{}",
                content_type="application/json",
                content_encoding="utf-8",
                meta=json.dumps(
                    {
                        "operation": "campaign",
                        "campaign_id": str(campaign.pk),
                        "recipient": recipient["email"],
                        "publication": "unattempted",
                        "stage": "awaiting publication",
                        "time_limit": 120,
                        "deadline": (
                            timezone.now() + timedelta(seconds=120)
                        ).isoformat(),
                    }
                ),
            )
            task_ids.append(task_id)
        GroupResult(
            group_id,
            [current_app.AsyncResult(task_id) for task_id in task_ids],
            app=current_app,
        ).save()
        LogEntry.record(
            actor_email=requester.email,
            action_flag=LogEntry.Action.ACTION,
            obj=campaign,
            change_message=(
                f"Requested {'test' if test_emails is not None else 'campaign'} "
                f"email to {len(task_ids)} recipients."
            ),
            details={"task_ids": task_ids, "group_id": group_id},
        )
        transaction.on_commit(partial(_publish, task_ids))
    return OperationReceipt(task_ids, group_id)
