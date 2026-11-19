import re
from pathlib import Path
from urllib.parse import urlsplit

from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from PIL import Image

from speleodb.campaigns.mail import render_message
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.operations import snapshot
from speleodb.campaigns.tests import EMAIL_TEMPLATE


def test_email_and_modal_render_valid_bundled_campaign_photos() -> None:
    campaign = DonationCampaign(
        email_main_subject="Support SpeleoDB",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        email_main_template=EMAIL_TEMPLATE,
    )
    _, email = render_message(
        snapshot(campaign),
        site_url="https://example.com/",
        unsubscribe="https://example.com/unsubscribe/",
    )
    modal = render_to_string(
        campaign.modal_template_name, {"donation_campaign": campaign}
    )
    for html in (email, modal):
        match = re.search(r'<img\s+src="([^"]+)"[^>]+alt="([^"]+)"', html)
        assert match is not None
        image_path = urlsplit(match[1]).path.removeprefix("/static/")
        assert image_path.startswith("campaigns/email_templates/assets/")
        assert "Marcelin Nebenhaus" in " ".join(html.split())
        description = " ".join(match[2].casefold().split())
        assert "cave diver" in description
        assert "underwater passage" in description
        asset = finders.find(image_path)
        assert isinstance(asset, str)
        with Image.open(Path(asset)) as image:
            image.verify()
