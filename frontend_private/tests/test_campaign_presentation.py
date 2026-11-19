"""Dashboard audience and template-owned campaign presentation."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationCampaignDismissal
from speleodb.campaigns.models import email_template_choices
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client


@pytest.mark.django_db
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_dashboard_campaign_dates_and_dismissal(client: Client, offset: int) -> None:
    user = UserFactory.create()
    client.force_login(user)
    day = timezone.localdate() + timedelta(days=offset)
    campaign = DonationCampaign.objects.create(
        email_main_subject="Support SpeleoDB",
        email_main_template=email_template_choices()[0][0],
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate?campaign_id=AJQDX9UZ2WAAE",
        start_date=day,
        end_date=day,
    )
    response = client.get(reverse("private:user_dashboard"))
    html = response.content.decode()
    assert ('id="donation-campaign"' in html) is (offset == 0)
    if offset == 0:
        assert '"shouldInvite": true' in html
        assert "SpeleoDB should stay free..." in html
        DonationCampaignDismissal.objects.create(campaign=campaign, user=user)
        html = client.get(reverse("private:user_dashboard")).content.decode()
        assert 'id="campaign-card-title"' in html
        assert '"shouldInvite": false' in html
        assert (
            'id="donation-campaign"'
            not in client.get(reverse("private:user_profile")).content.decode()
        )


def test_modal_renders_campaign_story_without_database_copy_fields() -> None:
    campaign = DonationCampaign(
        goal_usd=7200,
        donation_url="https://example.com/give?a=1&b=2",
        reminder_days=14,
    )
    html = render_to_string(
        "snippets/donation_campaign.html", {"donation_campaign": campaign}
    )
    assert "SpeleoDB should stay free..." in html
    assert 'href="https://example.com/give?a=1&amp;b=2"' in html
    assert "US $7,200" in html
    assert "Remind me in 14 days" in html
    assert "Connect your tools" in html
    assert "Ariane, Compass &amp; Stalagmight" in html
    assert "GIS connects your surveys" in html
    assert "Available offline" in html
    assert "Marcelin Nebenhaus" in html
    assert "Underwater Speleological and Archaeological Heritage Institute" in " ".join(
        html.split()
    )
    assert 'class="donation-impact-grid"' in html
    assert "data-campaign-story-back" in html
    assert "data-campaign-retry" in html
    assert "Every survey represents hours of exploration" in html
    assert "hard-earned discovery" not in html
