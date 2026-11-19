from __future__ import annotations

from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.utils import timezone

from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import email_template_choices


@pytest.fixture
def configured_campaign() -> DonationCampaign:
    today = timezone.localdate()
    return DonationCampaign(
        email_main_subject="Community appeal",
        email_main_template=email_template_choices()[0][0],
        donation_url="https://example.com/give",
        goal_usd=5000,
        start_date=today,
        end_date=today,
    )


def test_donor_clean_normalizes_addresses(
    configured_campaign: DonationCampaign,
) -> None:
    configured_campaign.donors = ["  Donor@Example.com ", "donor@example.com"]
    configured_campaign.clean()
    assert configured_campaign.donors == ["donor@example.com"]


@pytest.mark.django_db
def test_donor_addresses_are_normalized_validated_and_persisted(
    configured_campaign: DonationCampaign,
) -> None:
    configured_campaign.donors = [
        "  Donor@Example.com ",
        "donor@example.com",
        "second@example.com",
    ]
    configured_campaign.full_clean()
    configured_campaign.save()
    configured_campaign.refresh_from_db()
    assert configured_campaign.donors == ["donor@example.com", "second@example.com"]


@pytest.mark.parametrize(
    "donors", [{}, "donor@example.com", None, [1], [""], ["invalid"]]
)
def test_invalid_donor_lists_are_rejected(
    configured_campaign: DonationCampaign, donors: Any
) -> None:
    configured_campaign.donors = donors
    with pytest.raises(ValidationError) as error:
        configured_campaign.clean()
    assert "donors" in error.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("reminder_enabled", [False, True])
def test_empty_donors_and_complete_reminder_configuration_are_valid(
    configured_campaign: DonationCampaign, reminder_enabled: bool
) -> None:
    if reminder_enabled:
        configured_campaign.email_reminder_subject = "Before our campaign closes"
        configured_campaign.reminder_email_template = (
            configured_campaign.email_main_template
        )
    configured_campaign.full_clean()
    configured_campaign.save()
    configured_campaign.refresh_from_db()
    assert configured_campaign.donors == []
    assert str(configured_campaign) == "Community appeal"


@pytest.mark.parametrize(
    ("subject", "template_selected", "error_field"),
    [
        ("", True, "email_reminder_subject"),
        ("   ", True, "email_reminder_subject"),
        ("Reminder", False, "reminder_email_template"),
    ],
)
def test_incomplete_reminder_configuration_is_rejected(
    configured_campaign: DonationCampaign,
    subject: str,
    template_selected: bool,
    error_field: str,
) -> None:
    configured_campaign.email_reminder_subject = subject
    if template_selected:
        configured_campaign.reminder_email_template = (
            configured_campaign.email_main_template
        )
    with pytest.raises(ValidationError) as error:
        configured_campaign.clean()
    assert error_field in error.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("subject_only", [False, True])
def test_database_rejects_partial_reminder_update_and_preserves_valid_configuration(
    configured_campaign: DonationCampaign, subject_only: bool
) -> None:
    configured_campaign.save()
    update = (
        {"email_reminder_subject": "Reminder"}
        if subject_only
        else {"reminder_email_template": configured_campaign.email_main_template}
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        DonationCampaign.objects.filter(pk=configured_campaign.pk).update(**update)
    configured_campaign.refresh_from_db()
    assert configured_campaign.email_reminder_subject == ""
    assert configured_campaign.reminder_email_template == ""
