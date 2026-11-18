import re
from http import HTTPStatus

import pytest
from django.test import Client
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from speleodb.campaigns.models import CampaignDismissal
from speleodb.campaigns.models import DonationCampaign
from speleodb.users.tests.factories import UserFactory


@pytest.mark.django_db
@override_settings(CSRF_COOKIE_HTTPONLY=True)
def test_dashboard_supplies_csrf_token_for_session_dismissal() -> None:
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        headline="Support SpeleoDB",
        subject="Support",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today,
        end_date=today,
    )
    user = UserFactory.create()
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    page = client.get(reverse("private:user_dashboard"))
    assert page.status_code == HTTPStatus.OK
    url = f"/api/v2/user/donation-campaigns/{campaign.pk}/dismiss/"
    assert client.post(url).status_code == HTTPStatus.FORBIDDEN
    token = re.search(
        r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode()
    )
    assert token is not None, (
        "Dashboard must expose a masked token for its campaign POST"
    )
    assert (
        client.post(url, HTTP_X_CSRFTOKEN=token.group(1)).status_code
        == HTTPStatus.NO_CONTENT
    )
    assert CampaignDismissal.objects.filter(campaign=campaign, user=user).exists()
    assert not campaign.should_invite(user)
    assert (
        '"shouldInvite": false'
        in client.get(reverse("private:user_dashboard")).content.decode()
    )
