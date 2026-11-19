from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationCampaignDismissal
from speleodb.campaigns.models import DonationCampaignEmail
from speleodb.campaigns.tests import EMAIL_TEMPLATE
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client


@pytest.mark.django_db
@pytest.mark.parametrize("bulk", [False, True])
@pytest.mark.parametrize("superuser", [False, True])
def test_campaign_admin_deletion_requires_superuser(
    client: Client, bulk: bool, superuser: bool
) -> None:
    user = UserFactory.create(is_staff=True, is_superuser=superuser)
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="campaigns")
    )
    client.force_login(user)
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        email_main_subject="Support",
        email_main_template=EMAIL_TEMPLATE,
        goal_usd=5000,
        donation_url="https://example.com/donate",
        start_date=today,
        end_date=today,
    )
    dismissal = DonationCampaignDismissal.objects.create(campaign=campaign, user=user)
    history = DonationCampaignEmail.objects.create(
        campaign=campaign,
        email_type=DonationCampaignEmail.EmailType.MAIN,
        subject="Support",
        template=EMAIL_TEMPLATE,
        recipients=[user.email],
    )
    listing = reverse("admin:campaigns_donationcampaign_changelist")
    delete_url = reverse("admin:campaigns_donationcampaign_delete", args=[campaign.pk])
    if bulk:
        response = client.post(
            listing,
            {
                "action": "delete_selected",
                "_selected_action": [str(campaign.pk)],
                "post": "yes",
            },
        )
        assert response.status_code == (
            HTTPStatus.FOUND if superuser else HTTPStatus.FORBIDDEN
        )
    else:
        confirmation = client.get(delete_url)
        assert confirmation.status_code == (
            HTTPStatus.OK if superuser else HTTPStatus.FORBIDDEN
        )
        response = client.post(delete_url, {"post": "yes"})
        assert response.status_code == (
            HTTPStatus.FOUND if superuser else HTTPStatus.FORBIDDEN
        )
    assert DonationCampaign.objects.filter(pk=campaign.pk).exists() is not superuser
    assert (
        DonationCampaignDismissal.objects.filter(pk=dismissal.pk).exists()
        is not superuser
    )
    assert DonationCampaignEmail.objects.filter(pk=history.pk).exists() is not superuser
