from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import pytest
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Field
from django.test import override_settings
from django.utils import timezone

from speleodb.campaigns import models
from speleodb.campaigns.mail import render_message
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.operations import review_digest
from speleodb.campaigns.operations import snapshot
from speleodb.campaigns.tests import EMAIL_TEMPLATE

if TYPE_CHECKING:
    from pathlib import Path


def test_template_dropdown_discovers_only_uuid_html_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = f"{uuid.uuid4()}.html"
    second = f"{uuid.uuid4()}.html"
    for filename in (first, second, "notes.html", f"{uuid.uuid1()}.html"):
        (tmp_path / filename).write_text("<p>Campaign</p>")
    (tmp_path / f"{uuid.uuid4()}.txt").write_text("Not an HTML template")
    (tmp_path / f"{uuid.uuid4()}.html").mkdir()
    monkeypatch.setattr(models, "EMAIL_TEMPLATES_DIR", tmp_path)

    assert models.email_template_choices() == [
        (filename, filename) for filename in sorted((first, second))
    ]
    campaign_form = forms.modelform_factory(
        DonationCampaign, fields=["email_main_template", "reminder_email_template"]
    )
    before = campaign_form()
    assert isinstance(before.fields["email_main_template"].widget, forms.Select)
    assert before.fields["email_main_template"].required
    assert not before.fields["reminder_email_template"].required
    (tmp_path / second).unlink()
    after = campaign_form()
    rendered_options = str(after["email_main_template"])
    assert second not in rendered_options
    assert first in rendered_options


@pytest.mark.parametrize(
    "field_name", ["email_main_template", "reminder_email_template"]
)
@pytest.mark.parametrize("invalid_name", ["missing.html", "../email.html"])
def test_missing_or_outside_template_cannot_be_selected(
    field_name: str, invalid_name: str
) -> None:
    field = DonationCampaign._meta.get_field(field_name)  # noqa: SLF001 - model validation boundary
    assert isinstance(field, Field)
    with pytest.raises(ValidationError):
        field.clean(invalid_name, None)


def test_email_renders_dynamic_fields_and_unsubscribe() -> None:
    filename = EMAIL_TEMPLATE
    today = timezone.localdate()
    campaign = DonationCampaign(
        email_main_subject="Community & discovery",
        goal_usd=7200,
        donation_url="https://example.com/give?campaign=summer&source=email",
        email_main_template=filename,
        start_date=today,
        end_date=today,
    )
    plain, html = render_message(
        snapshot(campaign),
        site_url="https://example.com/",
        unsubscribe="https://example.com/unsubscribe/",
    )
    assert "SpeleoDB should stay free..." in html
    assert "<title>Community &amp; discovery</title>" in html
    assert "US $7,200" in html
    assert 'href="https://example.com/give?campaign=summer&amp;source=email"' in html
    assert "https://example.com/unsubscribe/" in html
    assert "Marcelin Nebenhaus" in " ".join(html.split())
    assert "501(c)(3)" in html
    assert "<table" not in plain
    assert "SpeleoDB should stay free..." in plain
    assert "US $7,200" in plain
    assert campaign.donation_url in plain
    assert "https://example.com/unsubscribe/" in plain


@override_settings(
    DEBUG=False,
    STORAGES={"staticfiles": {"BACKEND": "speleodb.utils.s3_storages.S3StaticStorage"}},
    AWS_S3_CUSTOM_DOMAIN="cdn.example.com",
    AWS_S3_URL_PROTOCOL="https:",
)
@pytest.mark.parametrize(
    "filename", [name for name, _label in models.email_template_choices()]
)
def test_email_photo_uses_production_static_storage_domain(filename: str) -> None:
    today = timezone.localdate()
    campaign = DonationCampaign(
        email_main_subject="Support SpeleoDB",
        goal_usd=5000,
        donation_url="https://example.com/give",
        email_main_template=filename,
        start_date=today,
        end_date=today,
    )
    _, html = render_message(
        snapshot(campaign),
        site_url="https://app.example.com/",
        unsubscribe="https://app.example.com/unsubscribe/",
    )
    images = re.findall(r'<img\b[^>]*\bsrc="([^"]+)"', html)
    assert images
    for image_url in images:
        assert image_url.startswith(
            "https://cdn.example.com/staticfiles/campaigns/email_templates/assets/"
        )
        asset_name = urlsplit(image_url).path.rsplit("/", 1)[-1]
        assert (models.EMAIL_TEMPLATES_DIR / "assets" / asset_name).is_file()


@pytest.mark.django_db
def test_template_edits_invalidate_review_without_changing_queued_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    filename = f"{uuid.uuid4()}.html"
    path = tmp_path / filename
    original = "<h1>{{ campaign.subject }}</h1><p>Original approved story</p>"
    path.write_text(original)
    monkeypatch.setattr(models, "EMAIL_TEMPLATES_DIR", tmp_path)
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        email_main_subject="Support SpeleoDB",
        goal_usd=5000,
        donation_url="https://example.com/give",
        email_main_template=filename,
        start_date=today,
        end_date=today,
    )
    approved = snapshot(campaign)
    digest = review_digest(campaign)
    assert approved["email_template_source"] == original
    path.write_text("<p>Replacement story</p>")
    assert review_digest(campaign) != digest
    assert snapshot(campaign)["email_template_source"] == "<p>Replacement story</p>"
    _, html = render_message(
        approved,
        site_url="https://example.com/",
        unsubscribe="https://example.com/unsubscribe/",
    )
    assert "Original approved story" in html
    assert "Replacement story" not in html
    path.unlink()
    with pytest.raises(ValueError, match="template"):
        snapshot(campaign)


def test_main_email_does_not_require_an_unused_reminder_template() -> None:
    campaign = DonationCampaign(
        email_main_subject="Main community appeal",
        email_main_template=EMAIL_TEMPLATE,
        email_reminder_subject="Closing soon",
        reminder_email_template=f"{uuid.uuid4()}.html",
        donation_url="https://example.com/give",
        goal_usd=7200,
    )
    plain, html = render_message(
        snapshot(campaign),
        site_url="https://example.com/",
        unsubscribe="https://example.com/preferences/",
    )
    assert campaign.donation_url in plain
    assert "<title>Main community appeal</title>" in html
    with pytest.raises(ValueError, match="available campaign email template"):
        snapshot(campaign, reminder=True)
