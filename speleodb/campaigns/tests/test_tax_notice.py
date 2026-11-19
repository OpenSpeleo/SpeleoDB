from django.template.loader import render_to_string

from speleodb.campaigns.mail import render_message
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.operations import snapshot
from speleodb.campaigns.tests import EMAIL_TEMPLATE


def test_tax_notice_appears_beside_campaign_actions() -> None:
    campaign = DonationCampaign(
        email_main_subject="Support SpeleoDB",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        email_main_template=EMAIL_TEMPLATE,
    )
    plain, html = render_message(
        snapshot(campaign),
        site_url="https://example.com/",
        unsubscribe="https://example.com/unsubscribe/",
    )
    modal = render_to_string(
        campaign.modal_template_name, {"donation_campaign": campaign}
    )
    for rendered in (plain, html, modal):
        output = " ".join(rendered.split())
        assert (
            "Underwater Speleological and Archaeological Heritage Institute" in output
        )
        assert "A 501(c)(3) nonprofit organization." in output
        assert (
            "Donations are tax-deductible to the extent permitted by U.S. law."
            in output
        )
