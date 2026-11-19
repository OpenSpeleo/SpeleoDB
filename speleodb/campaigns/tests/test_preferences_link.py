from __future__ import annotations

from http import HTTPStatus
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from speleodb.campaigns.mail import send_message
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.operations import snapshot
from speleodb.campaigns.tests import EMAIL_TEMPLATE
from speleodb.users.tests.factories import UserFactory


@pytest.mark.parametrize(
    "site_url", ["http://localhost:8000/", "https://www.speleodb.org/"]
)
def test_campaign_footer_opens_preferences_without_one_click_unsubscribe(
    site_url: str, mailoutbox: Any
) -> None:
    campaign = DonationCampaign(
        email_main_subject="Support SpeleoDB",
        goal_usd=5000,
        donation_url="https://example.com/give",
        email_main_template=EMAIL_TEMPLATE,
    )
    send_message(snapshot(campaign), email="reader@example.com", site_url=site_url)
    message = mailoutbox[0]
    preferences = site_url.rstrip("/") + reverse("private:user_preferences")
    assert f'href="{preferences}"' in message.alternatives[0].content
    assert preferences in message.body
    assert "List-Unsubscribe" not in message.extra_headers
    assert "List-Unsubscribe-Post" not in message.extra_headers


@pytest.mark.django_db
def test_preferences_link_requires_sign_in_and_does_not_change_preferences() -> None:
    user = UserFactory.create(email_on_speleodb_updates=True)
    client = Client(enforce_csrf_checks=True)
    url = reverse("private:user_preferences")
    response = client.get(url)
    assert response.status_code == HTTPStatus.FOUND
    assert "login" in response["Location"]
    user.refresh_from_db()
    assert user.email_on_speleodb_updates
    client.force_login(user)
    assert client.get(url).status_code == HTTPStatus.OK
    user.refresh_from_db()
    assert user.email_on_speleodb_updates
