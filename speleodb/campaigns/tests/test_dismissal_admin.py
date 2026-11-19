from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationCampaignDismissal
from speleodb.campaigns.models import DonationCampaignEmail
from speleodb.campaigns.models import email_template_choices
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client


@pytest.mark.django_db
def test_only_superuser_can_delete_dismissals_and_records_cannot_be_edited(
    admin_client: Client,
) -> None:
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        email_main_template=email_template_choices()[0][0],
        email_main_subject="Support",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today,
        end_date=today,
    )
    user = UserFactory.create()
    dismissal = DonationCampaignDismissal.objects.create(campaign=campaign, user=user)
    listing = reverse("admin:campaigns_donationcampaigndismissal_changelist")
    detail = reverse(
        "admin:campaigns_donationcampaigndismissal_change", args=[dismissal.pk]
    )
    assert listing in admin_client.get(reverse("admin:index")).content.decode()
    response = admin_client.get(listing)
    assert response.status_code == HTTPStatus.OK
    assert campaign.email_main_subject in response.content.decode()
    assert user.email in response.content.decode()
    assert admin_client.get(detail).status_code == HTTPStatus.OK
    assert (
        admin_client.post(detail, {"user": str(user.pk)}).status_code
        == HTTPStatus.FORBIDDEN
    )
    assert (
        admin_client.get(
            reverse("admin:campaigns_donationcampaigndismissal_add")
        ).status_code
        == HTTPStatus.FORBIDDEN
    )
    assert DonationCampaignDismissal.objects.filter(pk=dismissal.pk).exists()
    staff = UserFactory.create(is_staff=True, is_superuser=False)
    staff.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="campaigns",
            content_type__model="donationcampaigndismissal",
        )
    )
    admin_client.force_login(staff)
    assert admin_client.get(listing).status_code == HTTPStatus.FORBIDDEN
    assert admin_client.get(detail).status_code == HTTPStatus.FORBIDDEN
    deletion = reverse(
        "admin:campaigns_donationcampaigndismissal_delete", args=[dismissal.pk]
    )
    assert (
        admin_client.post(deletion, {"post": "yes"}).status_code == HTTPStatus.FORBIDDEN
    )
    assert DonationCampaignDismissal.objects.filter(pk=dismissal.pk).exists()
    admin_client.force_login(UserFactory.create(is_staff=True, is_superuser=True))
    assert admin_client.post(deletion, {"post": "yes"}).status_code == HTTPStatus.FOUND
    assert not DonationCampaignDismissal.objects.filter(pk=dismissal.pk).exists()
    assert campaign.should_invite(user)


@pytest.mark.django_db
def test_campaign_email_history_is_read_only_and_superuser_only(
    admin_client: Client,
) -> None:
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        email_main_template=email_template_choices()[0][0],
        email_main_subject="Support exploration",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today,
        end_date=today,
    )
    history = DonationCampaignEmail.objects.create(
        campaign=campaign,
        email_type=DonationCampaignEmail.EmailType.MAIN,
        subject="Sent community appeal",
        recipients=["recipient@example.com"],
        template=campaign.email_main_template,
    )
    original = DonationCampaignEmail.objects.values().get(pk=history.pk)
    listing = reverse("admin:campaigns_donationcampaignemail_changelist")
    detail = reverse("admin:campaigns_donationcampaignemail_change", args=[history.pk])
    assert admin_client.get(listing).status_code == HTTPStatus.OK
    response = admin_client.get(detail)
    assert response.status_code == HTTPStatus.OK
    assert b"recipient@example.com" in response.content
    assert b"Task results are no longer available." in response.content
    assert (
        admin_client.post(detail, {"subject": "Tampered"}).status_code
        == HTTPStatus.FORBIDDEN
    )
    for name in ("add", "delete"):
        args = [history.pk] if name == "delete" else []
        assert (
            admin_client.get(
                reverse(f"admin:campaigns_donationcampaignemail_{name}", args=args)
            ).status_code
            == HTTPStatus.FORBIDDEN
        )
    staff = UserFactory.create(is_staff=True, is_superuser=False)
    staff.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="campaigns",
            content_type__model="donationcampaignemail",
        )
    )
    admin_client.force_login(staff)
    assert admin_client.get(listing).status_code == HTTPStatus.FORBIDDEN
    assert admin_client.get(detail).status_code == HTTPStatus.FORBIDDEN
    assert DonationCampaignEmail.objects.values().get(pk=history.pk) == original
