"""Fundraiser content and durable account-level invitation preferences."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser

    from speleodb.users.models import User


def validate_story_cards(value: object) -> None:
    if not isinstance(value, list):
        raise ValidationError("Story cards must be a list.")
    for card in value:
        if (
            not isinstance(card, dict)
            or set(card) != {"title", "description", "icon"}
            or not all(isinstance(item, str) and item.strip() for item in card.values())
            or card["icon"] not in {"survey", "gis", "mobile"}
        ):
            raise ValidationError(
                "Each story card needs text title and description, "
                "and an icon: survey, gis, or mobile."
            )


class DonationCampaign(models.Model):
    # Automatic fields
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    photo = models.ImageField(
        upload_to="campaigns/photos/",
        blank=True,
        help_text="Publicly visible in campaign emails and dashboard invitations.",
    )
    photo_alt = models.CharField(max_length=250, blank=True)
    photo_credit = models.CharField(max_length=250, blank=True)

    headline = models.CharField(max_length=200)
    subject = models.CharField(max_length=200)
    preheader = models.CharField(max_length=250, blank=True)
    body = models.TextField(blank=True)
    popup_summary = models.TextField(blank=True)
    goal_usd = models.PositiveIntegerField()
    donation_url = models.URLField()
    recipient_name = models.CharField(
        "Donation recipient",
        max_length=250,
        blank=True,
        help_text="Legal name of the organization receiving donations.",
    )
    tax_deductibility_notice = models.TextField(
        blank=True,
        help_text=(
            "Public tax-status and deductibility statement "
            "shown beside donation actions."
        ),
    )
    brand_name = models.TextField(blank=True)
    contact_email = models.EmailField(blank=True)
    website_url = models.URLField(blank=True)
    tagline = models.TextField(blank=True)
    card_title = models.TextField(blank=True)
    card_summary = models.TextField(
        blank=True, help_text="Use {goal} for the formatted fundraising goal."
    )
    goal_currency_label = models.TextField(blank=True)
    goal_message = models.TextField(
        blank=True, help_text="Use {goal} for the formatted fundraising goal."
    )
    ownership_promise = models.TextField(blank=True)
    donate_label = models.TextField(blank=True)
    about_label = models.TextField(blank=True)
    story_label = models.TextField(blank=True)
    reminder_label = models.TextField(blank=True)
    back_label = models.TextField(blank=True)
    close_label = models.TextField(blank=True)
    new_tab_label = models.TextField(blank=True)
    retry_label = models.TextField(blank=True)
    dismissal_error = models.TextField(blank=True)
    recipient_intro = models.TextField(
        blank=True, help_text="Use {recipient} for the donation recipient name."
    )
    support_label = models.TextField(blank=True)
    sharing_message = models.TextField(blank=True)
    unsubscribe_label = models.TextField(blank=True)
    photo_credit_label = models.TextField(blank=True)
    story_kicker = models.TextField(blank=True)
    story_title = models.TextField(blank=True)
    story_summary = models.TextField(blank=True)
    story_goal_label = models.TextField(blank=True)
    story_goal_text = models.TextField(blank=True)
    story_promise = models.TextField(blank=True)
    story_cards = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_story_cards],
        help_text=(
            'Ordered cards: [{"title": "…", "description": "…", "icon": "survey"}]. '
            "Icons: survey, gis, mobile."
        ),
    )
    reminder_days = models.PositiveSmallIntegerField(
        default=7, validators=[MinValueValidator(1)]
    )

    start_date = models.DateField()
    end_date = models.DateField()

    launched_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_snapshot = models.JSONField(default=dict, editable=False)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="campaign_end_on_or_after_start",
            )
        ]

    def __str__(self) -> str:
        return self.headline

    @property
    def formatted_goal(self) -> str:
        return f"{self.goal_currency_label}{self.goal_usd:,}"

    @property
    def resolved_goal_message(self) -> str:
        return self.goal_message.replace("{goal}", self.formatted_goal)

    @property
    def resolved_card_summary(self) -> str:
        return self.card_summary.replace("{goal}", self.formatted_goal)

    @property
    def resolved_recipient_notice(self) -> str:
        return self.recipient_intro.replace("{recipient}", self.recipient_name)

    @property
    def photo_url(self) -> str:
        if not self.photo:
            return ""
        return (
            reverse("campaigns:photo", args=[self.pk])
            + "?"
            + urlencode({"v": self.photo.name})
        )

    def should_invite(self, user: User | AnonymousUser) -> bool:
        now = timezone.now()
        today = timezone.localdate(now)
        return (
            user.is_authenticated
            and self.start_date <= today <= self.end_date
            and not CampaignDismissal.objects.filter(
                campaign=self,
                user_id=user.pk,
                modified_date__gt=now - timedelta(days=self.reminder_days),
            ).exists()
        )


class CampaignDismissal(models.Model):
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
