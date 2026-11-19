from __future__ import annotations

import uuid
from datetime import timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import cast

import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone
from tablib.core import Dataset

from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationCampaignDismissal
from speleodb.campaigns.models import DonationCampaignEmail
from speleodb.campaigns.models import email_template_choices
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client

    from speleodb.campaigns.admin import DonationCampaignAdmin


@pytest.mark.django_db
def test_campaign_content_round_trip_preserves_email_history_and_dismissals() -> None:
    campaign_admin = cast(
        "DonationCampaignAdmin",
        admin.site._registry[DonationCampaign],  # noqa: SLF001 - registered admin contract
    )
    resource = campaign_admin.get_import_resource_classes(None)[0]()
    today = timezone.localdate()
    campaign_id = uuid.uuid4()
    data = Dataset(
        [
            str(campaign_id),
            "Support SpeleoDB",
            "Support our next chapter",
            "5000",
            "https://www.paypal.com/donate",
            email_template_choices()[0][0],
            email_template_choices()[0][0],
            str(today),
            str(today),
        ],
        headers=[
            "id",
            "email_main_subject",
            "email_reminder_subject",
            "goal_usd",
            "donation_url",
            "email_main_template",
            "reminder_email_template",
            "start_date",
            "end_date",
        ],
    )
    preview = resource.import_data(data, dry_run=True, raise_errors=True)
    assert preview.totals["new"] == 1
    assert not DonationCampaign.objects.exists()
    resource.import_data(data, dry_run=False, raise_errors=True)
    campaign = DonationCampaign.objects.get(pk=campaign_id)
    campaign.reminder_email_template = campaign.email_main_template
    history = DonationCampaignEmail.objects.create(
        campaign=campaign,
        email_type=DonationCampaignEmail.EmailType.MAIN,
        subject="Previously sent appeal",
        recipients=["donor@example.com"],
        template=campaign.email_main_template,
    )
    previous_history = DonationCampaignEmail.objects.values().get(pk=history.pk)
    campaign.save()
    dismissal = DonationCampaignDismissal.objects.create(
        campaign=campaign, user=UserFactory.create()
    )
    exported = Dataset().load(resource.export().csv, format="csv")
    row = exported.dict[0]
    assert row["email_main_subject"] == campaign.email_main_subject
    assert row["email_reminder_subject"] == campaign.email_reminder_subject
    assert row["modal_template"] == campaign.modal_template
    assert row["email_main_template"] == campaign.email_main_template
    assert row["reminder_email_template"] == campaign.reminder_email_template
    assert "launched_at" not in row
    assert "approved_snapshot" not in row
    row.update(
        email_main_subject="Updated campaign",
        email_reminder_subject="",
        donors='["donor@example.com"]',
        reminder_email_template="",
    )
    updated = Dataset(headers=exported.headers)
    updated.append([row[header] for header in exported.headers])
    result = resource.import_data(updated, dry_run=False, raise_errors=True)
    assert result.totals["update"] == 1
    assert DonationCampaign.objects.count() == 1
    campaign.refresh_from_db()
    assert campaign.email_main_subject == "Updated campaign"
    assert campaign.email_reminder_subject == ""
    assert campaign.donors == ["donor@example.com"]
    assert campaign.email_main_template == row["email_main_template"]
    assert campaign.reminder_email_template == ""
    assert DonationCampaignEmail.objects.values().get(pk=history.pk) == previous_history
    assert DonationCampaignDismissal.objects.filter(pk=dismissal.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("operation", ["import", "export", "process_import"])
def test_campaign_transfer_requires_superuser(
    admin_client: Client, operation: str
) -> None:
    url = reverse(f"admin:campaigns_donationcampaign_{operation}")
    if operation != "process_import":
        assert admin_client.get(url).status_code == HTTPStatus.OK
    staff = UserFactory.create(is_staff=True, is_superuser=False)
    admin_client.force_login(staff)
    response = (
        admin_client.post(url)
        if operation == "process_import"
        else admin_client.get(url)
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalid_change",
    [
        "modal_template",
        "second_campaign",
        "reversed_dates",
        "email_main_template",
        "reminder_email_template",
        "missing_email_reminder_subject",
    ],
)
def test_campaign_import_rejects_invalid_changes(invalid_change: str) -> None:
    campaign_admin = cast(
        "DonationCampaignAdmin",
        admin.site._registry[DonationCampaign],  # noqa: SLF001 - registered admin contract
    )
    resource = campaign_admin.get_import_resource_classes(None)[0]()
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        email_main_template=email_template_choices()[0][0],
        email_main_subject="Support SpeleoDB",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today,
        end_date=today,
    )
    row = resource.export().dict[0]
    if invalid_change == "second_campaign":
        row["id"] = str(uuid.uuid4())
    elif invalid_change == "reversed_dates":
        row["end_date"] = str(today - timedelta(days=1))
    elif invalid_change == "missing_email_reminder_subject":
        row["reminder_email_template"] = campaign.email_main_template
        row["email_reminder_subject"] = ""
    else:
        row[invalid_change] = "../email.html"
    data = Dataset(headers=list(row))
    data.append(list(row.values()))
    result = resource.import_data(data, dry_run=False)
    assert result.has_errors() or result.has_validation_errors()
    assert DonationCampaign.objects.count() == 1
    campaign.refresh_from_db()
    assert campaign.end_date == today


@pytest.mark.django_db
def test_staff_campaign_view_is_denied_even_with_change_permission(
    admin_client: Client,
) -> None:
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        email_main_template=email_template_choices()[0][0],
        email_main_subject="Unchanged campaign",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today,
        end_date=today,
    )
    staff = UserFactory.create(is_staff=True, is_superuser=False)
    staff.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="campaigns", content_type__model="donationcampaign"
        )
    )
    admin_client.force_login(staff)
    listing = reverse("admin:campaigns_donationcampaign_changelist")
    detail = reverse("admin:campaigns_donationcampaign_change", args=[campaign.pk])
    assert admin_client.get(listing).status_code == HTTPStatus.FORBIDDEN
    response = admin_client.get(detail)
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert (
        admin_client.post(detail, {"email_main_subject": "Changed"}).status_code
        == HTTPStatus.FORBIDDEN
    )
    for name in ("import", "export", "add", "delete"):
        args = [campaign.pk] if name == "delete" else []
        assert (
            admin_client.get(
                reverse(f"admin:campaigns_donationcampaign_{name}", args=args)
            ).status_code
            == HTTPStatus.FORBIDDEN
        )
    for route in ("admin:campaign_send", "admin:campaign_send_reminder"):
        assert (
            admin_client.post(
                reverse(route, args=[campaign.pk]),
                {"action": "test", "emails": "test@example.com"},
            ).status_code
            == HTTPStatus.FORBIDDEN
        )
    campaign.refresh_from_db()
    assert campaign.email_main_subject == "Unchanged campaign"
    admin_client.force_login(UserFactory.create(is_staff=True, is_superuser=True))
    assert b'name="_save"' in admin_client.get(detail).content
