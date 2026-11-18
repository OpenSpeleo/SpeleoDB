"""Dashboard audience and email presentation contracts."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from typing import TypedDict

import pytest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from speleodb.campaigns.models import CampaignDismissal
from speleodb.campaigns.models import DonationCampaign
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client


class EmailPreviewContext(TypedDict):
    campaign: DonationCampaign
    site_url: str
    photo_url: str
    unsubscribe_url: str


@pytest.mark.django_db
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_dashboard_campaign_dates_and_dismissal(client: Client, offset: int) -> None:
    user = UserFactory.create()
    client.force_login(user)
    day = timezone.localdate() + timedelta(days=offset)
    campaign = DonationCampaign.objects.create(
        headline="Preserve <discovery>",
        subject="Support SpeleoDB",
        body="Survey <work>",
        popup_summary="Our community",
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
        assert "Preserve &lt;discovery&gt;" in html
        CampaignDismissal.objects.create(campaign=campaign, user=user)
        html = client.get(reverse("private:user_dashboard")).content.decode()
        assert 'id="campaign-card-title"' in html
        assert '"shouldInvite": false' in html
        assert (
            'id="donation-campaign"'
            not in client.get(reverse("private:user_profile")).content.decode()
        )


def test_email_formats_preserve_text_and_escape_html() -> None:
    campaign = DonationCampaign(
        headline="Explore <together>",
        photo_credit="Marcelin Nebenhaus",
        subject="Support SpeleoDB",
        preheader="Keep surveys accessible",
        body="First <script>alert(1)</script>\n\nSecond paragraph",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate?campaign_id=AJQDX9UZ2WAAE",
    )
    context: EmailPreviewContext = {
        "campaign": campaign,
        "site_url": "https://www.speleodb.org",
        "photo_url": "https://www.speleodb.org/campaigns/example/photo/",
        "unsubscribe_url": "https://www.speleodb.org/unsubscribe/signed-token/",
    }
    html = render_to_string("campaigns/email.html", context)
    plain = render_to_string("campaigns/email.txt", context)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "First <script>alert(1)</script>" in plain
    for output in (html, plain):
        assert campaign.donation_url in output
        assert context["unsubscribe_url"] in output
        assert "Marcelin Nebenhaus" in output


def test_story_view_uses_visual_highlights_instead_of_full_email_copy() -> None:
    campaign = DonationCampaign(
        headline="Keep SpeleoDB free",
        goal_usd=5000,
        story_title="Our impact",
        story_cards=[
            {
                "title": "Survey tools",
                "description": "Ariane, Compass",
                "icon": "survey",
            },
            {"title": "GIS", "description": "Geography", "icon": "gis"},
            {"title": "Mobile", "description": "Available offline", "icon": "mobile"},
        ],
        body="Long campaign email copy belongs in the email.",
    )
    html = render_to_string(
        "snippets/donation_campaign_content.html", {"donation_campaign": campaign}
    )
    assert campaign.body not in html
    assert "Ariane, Compass" in html
    assert "GIS" in html
    assert "offline" in html
    assert 'class="donation-impact-grid"' in html
    assert "data-campaign-story-back" in html
