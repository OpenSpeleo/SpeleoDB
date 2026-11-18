import pytest
from django.template.loader import render_to_string
from django.utils import timezone

from speleodb.campaigns.mail import render_message
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.operations import review_digest
from speleodb.campaigns.operations import snapshot


@pytest.mark.django_db
def test_recipient_tax_notice_is_persisted_rendered_and_reviewed() -> None:
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        headline="Support SpeleoDB",
        subject="Support SpeleoDB",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today,
        end_date=today,
        recipient_intro="Donations are made to {recipient}.",
        recipient_name="Underwater Speleological and Archaeological Heritage Institute",
        tax_deductibility_notice=(
            "A 501(c)(3) nonprofit. Donations are tax-deductible "
            "to the extent permitted by U.S. law."
        ),
    )
    campaign.refresh_from_db()
    content = snapshot(campaign)
    plain, html = render_message(
        content,
        site_url="https://example.com/",
        unsubscribe="https://example.com/unsubscribe/",
    )
    modal = render_to_string(
        "snippets/donation_campaign_content.html", {"donation_campaign": campaign}
    )
    for output in (plain, html, modal):
        assert campaign.recipient_name in output
        assert campaign.tax_deductibility_notice in output
    digest = review_digest(campaign)
    campaign.tax_deductibility_notice = "Updated <script>notice</script>"
    assert review_digest(campaign) != digest
    _, html = render_message(
        snapshot(campaign),
        site_url="https://example.com/",
        unsubscribe="https://example.com/unsubscribe/",
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "501(c)(3)" in content["tax_deductibility_notice"]
