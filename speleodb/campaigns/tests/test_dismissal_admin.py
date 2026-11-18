from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from speleodb.campaigns.models import CampaignDismissal
from speleodb.campaigns.models import DonationCampaign
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client


@pytest.mark.django_db
def test_only_superuser_can_delete_dismissals_and_records_cannot_be_edited(
    admin_client: Client,
) -> None:
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        headline="Community fundraiser",
        subject="Support",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today,
        end_date=today,
    )
    user = UserFactory.create()
    dismissal = CampaignDismissal.objects.create(campaign=campaign, user=user)
    listing = reverse("admin:campaigns_campaigndismissal_changelist")
    detail = reverse("admin:campaigns_campaigndismissal_change", args=[dismissal.pk])
    assert listing in admin_client.get(reverse("admin:index")).content.decode()
    response = admin_client.get(listing)
    assert response.status_code == HTTPStatus.OK
    assert campaign.headline in response.content.decode()
    assert user.email in response.content.decode()
    assert admin_client.get(detail).status_code == HTTPStatus.OK
    assert (
        admin_client.post(detail, {"user": str(user.pk)}).status_code
        == HTTPStatus.FORBIDDEN
    )
    assert (
        admin_client.get(reverse("admin:campaigns_campaigndismissal_add")).status_code
        == HTTPStatus.FORBIDDEN
    )
    assert CampaignDismissal.objects.filter(pk=dismissal.pk).exists()
    staff = UserFactory.create(is_staff=True, is_superuser=False)
    staff.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="campaigns", content_type__model="campaigndismissal"
        )
    )
    admin_client.force_login(staff)
    assert admin_client.get(listing).status_code == HTTPStatus.FORBIDDEN
    assert admin_client.get(detail).status_code == HTTPStatus.FORBIDDEN
    deletion = reverse("admin:campaigns_campaigndismissal_delete", args=[dismissal.pk])
    assert (
        admin_client.post(deletion, {"post": "yes"}).status_code == HTTPStatus.FORBIDDEN
    )
    assert CampaignDismissal.objects.filter(pk=dismissal.pk).exists()
    admin_client.force_login(UserFactory.create(is_staff=True, is_superuser=True))
    assert admin_client.post(deletion, {"post": "yes"}).status_code == HTTPStatus.FOUND
    assert not CampaignDismissal.objects.filter(pk=dismissal.pk).exists()
    assert campaign.should_invite(user)
