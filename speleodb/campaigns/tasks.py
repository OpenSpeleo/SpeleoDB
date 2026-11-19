"""Campaign delivery uses the existing single-execution task result guard."""

from __future__ import annotations

from typing import Any

from celery import shared_task
from celery.exceptions import Ignore
from django.db import transaction

from speleodb.background_jobs.operation_execution import operation_execution
from speleodb.campaigns.mail import send_message
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationCampaignEmail
from speleodb.campaigns.operations import eligible_users


@shared_task(
    bind=True,
    # The execution guard owns STARTED; Celery must not write it before the claim.
    track_started=False,
    name="speleodb.campaigns.tasks.send_campaign_email",
    soft_time_limit=90,
    time_limit=120,
)
def send_campaign_email(
    self: Any,
    snapshot: dict[str, Any],
    email: str,
    site_url: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    with operation_execution(self.request.id) as execution:
        if execution is None:
            # Returning would let Celery overwrite the original result with SUCCESS.
            raise Ignore
        is_test = execution.metadata["is_test"]
        campaign = (
            None
            if is_test
            else DonationCampaign.objects.get(pk=execution.metadata["campaign_id"])
        )
        donor = campaign is not None and email.strip().casefold() in {
            address.strip().casefold() for address in campaign.donors
        }
        if donor or (
            user_id
            and not eligible_users(project_users_only=snapshot["project_users_only"])
            .filter(pk=user_id, email=email)
            .exists()
        ):
            summary = {
                "outcome": "skipped",
                "reason": ("Recipient donated or account eligibility changed."),
            }
        else:
            execution.progress("sending")
            summary = send_message(snapshot, email=email, site_url=site_url)
        with transaction.atomic():
            if not is_test and summary["outcome"] in {
                "provider-accepted",
                "backend-accepted",
            }:
                # Recipient tasks share one batch row, including across worker replicas.
                record, _ = (
                    DonationCampaignEmail.objects.select_for_update().get_or_create(
                        pk=execution.metadata["group_id"],
                        defaults={
                            "campaign_id": execution.metadata["campaign_id"],
                            "email_type": (
                                DonationCampaignEmail.EmailType.REMINDER
                                if snapshot["is_reminder"]
                                else DonationCampaignEmail.EmailType.MAIN
                            ),
                            "subject": snapshot["subject"],
                            "template": snapshot["template"],
                        },
                    )
                )
                if email.casefold() not in {
                    address.casefold() for address in record.recipients
                }:
                    record.recipients.append(email)
                    record.save(update_fields=["recipients", "modified_date"])
            execution.complete(summary)
        return summary
