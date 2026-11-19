"""Fundraiser content and durable account-level invitation preferences."""

from __future__ import annotations

import uuid
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.core.validators import validate_email
from django.db import models
from django.utils import timezone

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser

    from speleodb.users.models import User


EMAIL_TEMPLATES_DIR = (
    Path(__file__).resolve().parent.parent / "templates/campaigns/email_templates"
)
MODAL_TEMPLATES_DIR = (
    Path(__file__).resolve().parent.parent / "templates/campaigns/modal_templates"
)
DEFAULT_MODAL_TEMPLATE = "df63aaf1-de24-49d4-b695-315dee59441e.html"


def campaign_template_choices(directory: Path) -> list[tuple[str, str]]:
    choices: list[tuple[str, str]] = []
    for path in sorted(directory.glob("*.html")):
        if not path.is_file():
            continue
        try:
            identifier = uuid.UUID(path.stem)
        except ValueError:
            continue
        if identifier.version == 4 and str(identifier) == path.stem:  # noqa: PLR2004 - UUID4 filename contract.
            choices.append((path.name, path.name))
    return choices


def email_template_choices() -> list[tuple[str, str]]:
    return campaign_template_choices(EMAIL_TEMPLATES_DIR)


def modal_template_choices() -> list[tuple[str, str]]:
    return campaign_template_choices(MODAL_TEMPLATES_DIR)


class DonationCampaign(models.Model):
    # Automatic fields
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    start_date = models.DateField()
    end_date = models.DateField()

    # List of emails to NOT re-email again, they donated.
    donors = models.JSONField(default=list, blank=True, editable=True)

    donation_url = models.URLField("Campaign action URL")
    goal_usd = models.PositiveIntegerField("Financial goal (USD)")

    # Visual Remind People on Dashboard Connection
    reminder_days = models.PositiveSmallIntegerField(
        default=7, validators=[MinValueValidator(1)]
    )

    modal_template = models.CharField(
        "Modal template",
        max_length=41,
        choices=modal_template_choices,
        default=DEFAULT_MODAL_TEMPLATE,
    )

    # ---------------- Main Campaign Email ------------------ #
    email_main_subject = models.CharField("Email subject", max_length=200)
    email_main_template = models.CharField(
        max_length=41,
        choices=email_template_choices,
    )

    # ---------------- Reminder Campaign Email ------------------ #
    email_reminder_subject = models.CharField(
        "Reminder email subject",
        max_length=200,
        blank=True,
        help_text="Required when a reminder email template is selected.",
    )

    reminder_email_template = models.CharField(
        max_length=41,
        choices=email_template_choices,
        blank=True,
    )

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="campaign_end_on_or_after_start",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(reminder_email_template="", email_reminder_subject="")
                    | (
                        ~models.Q(reminder_email_template="")
                        & ~models.Q(email_reminder_subject="")
                    )
                ),
                name="campaign_complete_reminder_email",
            ),
        ]

    def __str__(self) -> str:
        return self.email_main_subject

    def clean(self) -> None:
        super().clean()
        self.email_reminder_subject = self.email_reminder_subject.strip()
        if self.reminder_email_template and not self.email_reminder_subject:
            raise ValidationError(
                {"email_reminder_subject": "Enter a reminder email subject."}
            )
        if self.email_reminder_subject and not self.reminder_email_template:
            raise ValidationError(
                {"reminder_email_template": "Select a reminder email template."}
            )
        if not isinstance(self.donors, list) or not all(
            isinstance(email, str) for email in self.donors
        ):
            raise ValidationError({"donors": "Enter a list of donor email addresses."})
        addresses: dict[str, None] = {}
        for email in self.donors:
            address = email.strip().casefold()
            try:
                validate_email(address)
            except ValidationError as error:
                raise ValidationError({"donors": error.messages}) from error
            addresses.setdefault(address, None)
        self.donors = list(addresses)

    @property
    def formatted_goal(self) -> str:
        return f"US ${self.goal_usd:,}"

    @property
    def modal_template_name(self) -> str:
        if self.modal_template not in dict(modal_template_choices()):
            raise ValueError("Select an available campaign modal template.")
        return f"campaigns/modal_templates/{self.modal_template}"

    def email_template_source(self, filename: str) -> str:
        if filename not in dict(email_template_choices()):
            raise ValueError("Select an available campaign email template.")
        return (EMAIL_TEMPLATES_DIR / filename).read_text(encoding="utf-8")

    def should_invite(self, user: User | AnonymousUser) -> bool:
        now = timezone.now()
        today = timezone.localdate(now)
        return (
            user.is_authenticated
            and self.start_date <= today <= self.end_date
            and not DonationCampaignDismissal.objects.filter(
                campaign=self,
                user_id=user.pk,
                modified_date__gt=now - timedelta(days=self.reminder_days),
            ).exists()
        )


class DonationCampaignDismissal(models.Model):
    # Automatic fields
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )
    campaign = models.ForeignKey(DonationCampaign, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "user"], name="unique_campaign_user_dismissal"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id}: {self.campaign_id}"


class DonationCampaignEmail(models.Model):
    # Automatic fields
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    class EmailType(models.TextChoices):
        MAIN = "MAIN", "Main"
        REMINDER = "REMINDER", "Reminder"

    email_type = models.CharField(max_length=16, choices=EmailType.choices)

    campaign = models.ForeignKey(
        DonationCampaign, on_delete=models.CASCADE, editable=False
    )

    subject = models.CharField(max_length=200, blank=False, null=False, editable=False)
    recipients = models.JSONField(default=list, editable=False)
    template = models.CharField(max_length=41, blank=False, null=False, editable=False)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self) -> str:
        return f"{self.get_email_type_display()}: {self.subject}"
