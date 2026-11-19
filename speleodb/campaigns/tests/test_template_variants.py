from __future__ import annotations

from typing import Any

import pytest
from django.utils.html import escape

from speleodb.campaigns.mail import send_message
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import email_template_choices
from speleodb.campaigns.operations import snapshot


def test_reminder_snapshot_uses_its_own_subject() -> None:
    filename = email_template_choices()[0][0]
    campaign = DonationCampaign(
        email_main_subject="Main invitation",
        email_main_template=filename,
        reminder_email_template=filename,
        goal_usd=5000,
    )
    campaign.email_reminder_subject = "The next discovery starts with you."
    assert snapshot(campaign)["subject"] == "Main invitation"
    assert (
        snapshot(campaign, reminder=True)["subject"] == campaign.email_reminder_subject
    )


@pytest.mark.parametrize(
    "template_name", [name for name, _ in email_template_choices()]
)
def test_selectable_email_templates_preserve_campaign_and_preferences_links(
    template_name: str,
    mailoutbox: Any,
) -> None:
    campaign = DonationCampaign(
        email_main_subject="Our community & its next discovery",
        goal_usd=7200,
        donation_url="https://example.com/give?campaign=community&source=email",
        email_main_template=template_name,
    )
    send_message(
        snapshot(campaign), email="reader@example.com", site_url="https://example.com/"
    )
    message = mailoutbox[0]
    html = message.alternatives[0].content
    assert message.subject == campaign.email_main_subject
    assert f"<title>{escape(campaign.email_main_subject)}</title>" in html
    assert "US $7,200" in html
    assert 'href="https://example.com/give?campaign=community&amp;source=email"' in html
    assert 'href="https://example.com/private/preferences/"' in html
    assert "Marcelin Nebenhaus" in " ".join(html.split())
    assert "Underwater Speleological and Archaeological Heritage Institute" in " ".join(
        html.split()
    )
    assert "501(c)(3)" in html
    assert "{{" not in html
    assert "<script" not in html.lower()
    assert "@media" not in message.body
    assert "!important" not in message.body
    assert "US $7,200" in message.body
    assert campaign.donation_url in message.body
    assert "https://example.com/private/preferences/" in message.body
