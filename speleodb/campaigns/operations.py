"""Reviewed campaign submissions with per-review replay prevention."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import timedelta
from functools import partial
from typing import Any
from uuid import UUID
from uuid import uuid4

from celery import current_app
from celery.result import GroupResult
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Exists
from django.db.models import OuterRef
from django.db.models import QuerySet
from django.utils import timezone
from django_celery_results.models import TaskResult

from speleodb.background_jobs.operations import OperationReceipt
from speleodb.background_jobs.operations import _publish
from speleodb.campaigns.mail import CONTENT_FIELDS
from speleodb.campaigns.models import DonationCampaign
from speleodb.common.enums import TaskResultStatus
from speleodb.surveys.models import TeamProjectPermission
from speleodb.surveys.models import UserProjectPermission
from speleodb.users.models import LogEntry
from speleodb.users.models import User

TASK_NAME = "speleodb.campaigns.tasks.send_campaign_email"


def eligible_users(*, project_users_only: bool = False) -> QuerySet[User]:
    users = User.objects.filter(email_on_speleodb_updates=True).exclude(email="")
    if project_users_only:
        direct_access = UserProjectPermission.objects.filter(
            target_id=OuterRef("pk"), is_active=True, project__is_active=True
        )
        team_access = TeamProjectPermission.objects.filter(
            target__memberships__user_id=OuterRef("pk"),
            target__memberships__is_active=True,
            is_active=True,
            project__is_active=True,
        )
        users = users.filter(Exists(direct_access) | Exists(team_access))
    return users


def audience(
    campaign: DonationCampaign, *, project_users_only: bool = False
) -> list[dict[str, str]]:
    recipients: dict[str, dict[str, str]] = {}
    donors = {address.strip().casefold() for address in campaign.donors}
    for user in (
        eligible_users(project_users_only=project_users_only).order_by("pk").iterator()
    ):
        if user.email.strip().casefold() in donors:
            continue
        recipients.setdefault(
            user.email.casefold(), {"user_id": str(user.pk), "email": user.email}
        )
    return list(recipients.values())


def snapshot(
    campaign: DonationCampaign,
    *,
    reminder: bool = False,
    project_users_only: bool = False,
) -> dict[str, Any]:
    if reminder and not campaign.reminder_email_template:
        raise ValueError("Select and save a reminder email template before sending.")
    if reminder and not campaign.email_reminder_subject.strip():
        raise ValueError("Enter and save a reminder email subject before sending.")
    return {
        "is_reminder": reminder,
        "project_users_only": project_users_only,
        **{field: deepcopy(getattr(campaign, field)) for field in CONTENT_FIELDS},
        "subject": campaign.email_reminder_subject
        if reminder
        else campaign.email_main_subject,
        "template": campaign.reminder_email_template
        if reminder
        else campaign.email_main_template,
        "formatted_goal": campaign.formatted_goal,
        "email_template_source": campaign.email_template_source(
            campaign.reminder_email_template
            if reminder
            else campaign.email_main_template
        ),
    }


def review_digest(
    campaign: DonationCampaign,
    *,
    reminder: bool = False,
    project_users_only: bool = False,
) -> str:
    data = {
        "content": snapshot(
            campaign, reminder=reminder, project_users_only=project_users_only
        ),
        "audience": audience(campaign, project_users_only=project_users_only),
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
    reminder: bool = False,
    project_users_only: bool = False,
    send_id: str | None = None,
) -> OperationReceipt:
    if not requester.is_active or not requester.is_superuser:
        raise PermissionDenied
    group_id = str(UUID(send_id)) if send_id is not None else str(uuid4())
    with transaction.atomic():
        campaign = DonationCampaign.objects.select_for_update().get(pk=campaign_id)
        # Test recipients are explicit and never subject to account audience filters.
        project_users_only = project_users_only and test_emails is None
        content = snapshot(
            campaign, reminder=reminder, project_users_only=project_users_only
        )
        recipients: list[dict[str, Any]]
        if test_emails is None:
            if send_id is None:
                raise ValueError("Review the campaign before sending.")
            if LogEntry.objects.filter(
                model_label="campaigns.donationcampaign",
                object_id=str(campaign.pk),
                details__group_id=group_id,
            ).exists():
                raise ValueError(
                    "This review was already submitted. Review again to resend."
                )
            if digest != review_digest(
                campaign, reminder=reminder, project_users_only=project_users_only
            ):
                raise ValueError("Campaign content or audience changed. Review again.")
            recipients = audience(campaign, project_users_only=project_users_only)
            if not recipients:
                raise ValueError("No eligible recipients.")
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
                        "group_id": group_id,
                        "is_test": test_emails is not None,
                        "is_reminder": reminder,
                        "project_users_only": project_users_only,
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
                f"{'reminder ' if reminder else ''}email to {len(task_ids)} recipients."
            ),
            details={
                "task_ids": task_ids,
                "group_id": group_id,
                "is_reminder": reminder,
                "project_users_only": project_users_only,
            },
        )
        transaction.on_commit(partial(_publish, task_ids))
    return OperationReceipt(task_ids, group_id)
