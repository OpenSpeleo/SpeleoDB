from contextlib import closing
from http import HTTPStatus
from io import BytesIO

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import InMemoryStorage
from django.http import FileResponse
from django.template.loader import render_to_string
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from speleodb.campaigns.mail import render_message
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.operations import snapshot


@pytest.mark.django_db(transaction=True)
def test_uploaded_photo_is_public_and_used_in_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    field = DonationCampaign._meta.get_field("photo")  # noqa: SLF001 - Django field storage boundary
    monkeypatch.setattr(field, "storage", InMemoryStorage())
    with BytesIO() as buffer:
        Image.new("RGB", (2, 2)).save(buffer, format="PNG")
        data = buffer.getvalue()
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        headline="Support exploration",
        subject="Support SpeleoDB",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today,
        end_date=today,
        photo=ContentFile(data, name="cave.png"),
        photo_alt="Cave passage",
        photo_credit="Photographer <name>",
        photo_credit_label="Image by",
    )
    url = reverse("campaigns:photo", args=[campaign.pk])
    with closing(Client().get(url)) as response:
        assert response.status_code == HTTPStatus.OK
        assert isinstance(response, FileResponse)
        assert b"".join(response.streaming_content) == data
        assert response["Content-Type"] == "image/png"
    plain, html = render_message(
        snapshot(campaign),
        site_url="https://example.com/",
        unsubscribe="https://example.com/unsubscribe/",
    )
    assert f"https://example.com{url}" in html
    assert "Cave passage" in html
    assert "Photographer" in plain
    previous_url = snapshot(campaign)["photo_url"]
    campaign.photo.save("replacement.png", ContentFile(data))
    replacement_url = snapshot(campaign)["photo_url"]
    assert replacement_url != previous_url
    modal = render_to_string(
        "snippets/donation_campaign_content.html", {"donation_campaign": campaign}
    )
    assert replacement_url in modal
    assert previous_url not in modal
    assert "Image by Photographer &lt;name&gt;" in modal
    campaign.photo = ""
    campaign.save()
    assert Client().get(url).status_code == HTTPStatus.NOT_FOUND
    _, html = render_message(
        snapshot(campaign),
        site_url="https://example.com/",
        unsubscribe="https://example.com/unsubscribe/",
    )
    assert "<img" not in html
    modal = render_to_string(
        "snippets/donation_campaign_content.html", {"donation_campaign": campaign}
    )
    assert "Image by" not in modal
    assert "Photographer" not in modal
