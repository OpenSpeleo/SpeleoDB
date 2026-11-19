from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import pytest
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.templatetags.static import static
from PIL import Image

from speleodb.campaigns.mail import render_message
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.operations import snapshot
from speleodb.campaigns.tests import EMAIL_TEMPLATE

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings


@pytest.mark.parametrize(
    "storage_backend",
    [
        pytest.param(
            "django.contrib.staticfiles.storage.StaticFilesStorage", id="filesystem"
        ),
        pytest.param("speleodb.utils.s3_storages.S3StaticStorage", id="s3"),
    ],
)
def test_email_and_modal_render_valid_bundled_campaign_photos(
    settings: Settings, storage_backend: str
) -> None:
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": storage_backend},
    }
    settings.STATIC_URL = "/static/"
    settings.AWS_S3_CUSTOM_DOMAIN = "assets.example.com/test-bucket"
    settings.AWS_S3_URL_PROTOCOL = "https:"
    asset_prefix = "campaigns/email_templates/assets/"
    url_prefix = urlsplit(static(asset_prefix)).path
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
        image_path = urlsplit(match[1]).path
        assert image_path.startswith(url_prefix)
        assert "Marcelin Nebenhaus" in " ".join(html.split())
        description = " ".join(match[2].casefold().split())
        assert "cave diver" in description
        assert "underwater passage" in description
        asset = finders.find(asset_prefix + image_path.removeprefix(url_prefix))
        assert isinstance(asset, str)
        with Image.open(Path(asset)) as image:
            image.verify()
