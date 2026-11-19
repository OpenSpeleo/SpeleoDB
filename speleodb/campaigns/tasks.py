"""Campaign delivery uses the existing single-execution task result guard."""

from __future__ import annotations

from typing import Any

from celery import shared_task
from celery.exceptions import Ignore
from django.db import transaction
from django.utils import timezone

from speleodb.background_jobs.operation_execution import operation_execution
from speleodb.campaigns.letter_operations import LETTER_TASK
from speleodb.campaigns.letter_operations import LETTER_TIME_LIMIT
from speleodb.campaigns.letter_operations import letter_review_digest
from speleodb.campaigns.letter_rendering import example_letter
from speleodb.campaigns.letter_rendering import render_letter_pdf
from speleodb.campaigns.mail import send_message
from speleodb.campaigns.mail import send_rendered_message
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationCampaignEmail
from speleodb.campaigns.models import DonationThankYouLetters
from speleodb.campaigns.models import DonationThankYouTemplate
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


@shared_task(
    bind=True,
    track_started=False,
    name=LETTER_TASK,
    soft_time_limit=90,
    time_limit=LETTER_TIME_LIMIT,
)
def send_donation_letter(
    self: Any,
    object_id: str,
    *,
    recipient: str,
    subject: str,
    plain: str,
    html: str,
    preview_model: str | None = None,
    review_digest: str = "",
) -> dict[str, Any]:
    with operation_execution(self.request.id) as execution:
        if execution is None:
            raise Ignore
        execution.progress("sending")
        with transaction.atomic():
            if preview_model == "template":
                template = DonationThankYouTemplate.objects.get(pk=object_id)
                if letter_review_digest(template) != review_digest:
                    raise ValueError("The template changed. Request a new preview.")
                letter = example_letter(template)
            else:
                letters = DonationThankYouLetters.objects.select_related("template")
                if not preview_model:
                    # Editing an issued gift and delivering its confirmed attachment
                    # must agree on the recipient and PDF until the mailer accepts it.
                    letters = letters.select_for_update(of=("self",))
                letter = letters.get(pk=object_id)
                if preview_model and letter_review_digest(letter) != review_digest:
                    raise ValueError("The draft changed. Request a new preview.")
            if preview_model:
                # Queued previews use the subject verified by the review digest.
                subject = letter.template.email_subject
                pdf = render_letter_pdf(letter)
            else:
                if str(letter.last_task_id) != self.request.id:
                    summary = {
                        "outcome": "skipped",
                        "reason": (
                            "The acknowledgment was regenerated "
                            "or a newer send was requested."
                        ),
                    }
                    execution.complete(summary)
                    return summary
                with letter.pdf.open("rb") as archive:
                    pdf = archive.read()
            result = send_rendered_message(
                subject=subject,
                email=recipient,
                plain=plain,
                html=html,
                attachment=(
                    f"donation-acknowledgment-{letter.pk}.pdf",
                    pdf,
                    "application/pdf",
                ),
            )
            if not preview_model:
                DonationThankYouLetters.objects.filter(pk=letter.pk).update(
                    last_sent_at=timezone.now()
                )
            execution.complete(result)
            return result
