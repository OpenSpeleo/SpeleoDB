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

from speleodb.campaigns.models import CampaignDismissal
from speleodb.campaigns.models import DonationCampaign
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client

    from speleodb.campaigns.admin import DonationCampaignAdmin


@pytest.mark.django_db
def test_campaign_content_round_trip_preserves_launch_and_dismissals() -> None:
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
            "Support exploration",
            "Support SpeleoDB",
            "5000",
            "https://www.paypal.com/donate",
            str(today),
            str(today),
        ],
        headers=[
            "id",
            "headline",
            "subject",
            "goal_usd",
            "donation_url",
            "start_date",
            "end_date",
        ],
    )
    preview = resource.import_data(data, dry_run=True, raise_errors=True)
    assert preview.totals["new"] == 1
    assert not DonationCampaign.objects.exists()
    resource.import_data(data, dry_run=False, raise_errors=True)
    campaign = DonationCampaign.objects.get(pk=campaign_id)
    campaign.about_label = "About our custom appeal"
    campaign.story_cards = [
        {"title": "Custom card", "description": "Custom detail", "icon": "gis"}
    ]
    campaign.body = "First paragraph.\nSecond paragraph, with a comma."
    campaign.photo = "campaigns/photos/cave.png"
    campaign.photo_alt = "Cave passage"
    campaign.photo_credit = "Photographer"
    campaign.launched_at = timezone.now()
    campaign.approved_snapshot = {"headline": "Approved copy", "group_id": "receipt"}
    campaign.save()
    dismissal = CampaignDismissal.objects.create(
        campaign=campaign, user=UserFactory.create()
    )
    launched_at = campaign.launched_at
    approved_snapshot = campaign.approved_snapshot
    exported = Dataset().load(resource.export().csv, format="csv")
    row = exported.dict[0]
    assert row["body"] == campaign.body
    assert row["photo"] == campaign.photo.name
    assert row["photo_alt"] == campaign.photo_alt
    assert row["photo_credit"] == campaign.photo_credit
    assert row["launched_at"]
    row.update(headline="Updated campaign", launched_at="", approved_snapshot="{}")
    updated = Dataset(headers=exported.headers)
    updated.append([row[header] for header in exported.headers])
    result = resource.import_data(updated, dry_run=False, raise_errors=True)
    assert result.totals["update"] == 1
    assert DonationCampaign.objects.count() == 1
    campaign.refresh_from_db()
    assert campaign.headline == "Updated campaign"
    assert campaign.body == row["body"]
    assert campaign.about_label == "About our custom appeal"
    assert campaign.story_cards == [
        {"title": "Custom card", "description": "Custom detail", "icon": "gis"}
    ]
    assert campaign.launched_at == launched_at
    assert campaign.approved_snapshot == approved_snapshot
    assert CampaignDismissal.objects.filter(pk=dismissal.pk).exists()


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
@pytest.mark.parametrize("invalid_change", ["second_campaign", "reversed_dates"])
def test_campaign_import_rejects_invalid_changes(invalid_change: str) -> None:
    campaign_admin = cast(
        "DonationCampaignAdmin",
        admin.site._registry[DonationCampaign],  # noqa: SLF001 - registered admin contract
    )
    resource = campaign_admin.get_import_resource_classes(None)[0]()
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        headline="Support exploration",
        subject="Support SpeleoDB",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today,
        end_date=today,
    )
    row = resource.export().dict[0]
    if invalid_change == "second_campaign":
        row["id"] = str(uuid.uuid4())
    else:
        row["end_date"] = str(today - timedelta(days=1))
    data = Dataset(headers=list(row))
    data.append(list(row.values()))
    result = resource.import_data(data, dry_run=False)
    assert result.has_errors() or result.has_validation_errors()
    assert DonationCampaign.objects.count() == 1
    campaign.refresh_from_db()
    assert campaign.end_date == today


@pytest.mark.django_db
def test_staff_campaign_view_is_read_only_even_with_change_permission(
    admin_client: Client,
) -> None:
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        headline="Unchanged campaign",
        subject="Support",
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
    assert admin_client.get(listing).status_code == HTTPStatus.OK
    response = admin_client.get(detail)
    assert response.status_code == HTTPStatus.OK
    assert b'name="_save"' not in response.content
    assert (
        admin_client.post(detail, {"headline": "Changed"}).status_code
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
    assert (
        admin_client.post(
            reverse("admin:campaign_send", args=[campaign.pk]),
            {"action": "test", "emails": "test@example.com"},
        ).status_code
        == HTTPStatus.FORBIDDEN
    )
    campaign.refresh_from_db()
    assert campaign.headline == "Unchanged campaign"
    admin_client.force_login(UserFactory.create(is_staff=True, is_superuser=True))
    assert b'name="_save"' in admin_client.get(detail).content
