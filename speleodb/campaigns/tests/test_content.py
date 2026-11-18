import pytest
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils import timezone

from speleodb.campaigns.mail import render_message
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.operations import review_digest
from speleodb.campaigns.operations import snapshot


@pytest.mark.django_db
def test_all_campaign_surfaces_use_persisted_content() -> None:
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        headline="Custom headline",
        subject="Custom subject",
        goal_usd=7200,
        donation_url="https://example.com/give",
        start_date=today,
        end_date=today,
        brand_name="Custom brand",
        contact_email="giving@example.com",
        website_url="https://example.com/",
        tagline="Custom tagline",
        card_title="Custom card",
        card_summary="Target: {goal}",
        goal_currency_label="USD ",
        goal_message="Raise {goal} together",
        ownership_promise="Custom ownership",
        donate_label="Give now",
        about_label="Learn about our work",
        story_label="Our impact",
        reminder_label="Later",
        back_label="Return",
        close_label="Close appeal",
        new_tab_label="New window",
        retry_label="Retry save",
        dismissal_error="Save failed",
        recipient_name="Custom foundation",
        recipient_intro="Recipient: {recipient}",
        support_label="Support our work",
        sharing_message="Tell a friend",
        unsubscribe_label="Email preferences",
        photo_credit_label="Image by",
        story_kicker="Our progress",
        story_title="Custom story\nTogether",
        story_summary="A short overview",
        story_goal_label="Our target",
        story_goal_text="Keep this available",
        story_promise="A lasting promise",
        story_cards=[
            {"title": "Custom <card>", "description": "Custom detail", "icon": "gis"}
        ],
    )
    campaign.refresh_from_db()
    html = render_to_string(
        "snippets/donation_campaign.html", {"donation_campaign": campaign}
    )
    plain, email_html = render_message(
        snapshot(campaign),
        site_url="https://example.com/",
        unsubscribe="https://example.com/preferences/",
    )
    for output in (html, plain, email_html):
        assert "Custom tagline" in output
        assert "Raise USD 7,200 together" in output
        assert "Give now" in output
        assert "Recipient: Custom foundation" in output
        assert "Donate with PayPal" not in output
        assert "Explore as One" not in output
    assert "Custom &lt;card&gt;" in html
    assert "Custom detail" in html
    assert "Connect your tools" not in html
    assert "Custom card" in html
    assert "Learn about our work" in html
    assert "Later" in html
    for output in (plain, email_html):
        assert "Custom brand" in output
        assert "giving@example.com" in output
        assert "Email preferences" in output
    digest = review_digest(campaign)
    campaign.story_cards[0]["title"] = "Changed impact"
    assert review_digest(campaign) != digest


def test_story_cards_reject_invalid_structure() -> None:
    field = DonationCampaign._meta.get_field("story_cards")  # noqa: SLF001 - Django field validation boundary
    with pytest.raises(ValidationError):
        field.clean(
            [{"title": "Title", "description": "Detail", "icon": "unrecognized"}], None
        )
