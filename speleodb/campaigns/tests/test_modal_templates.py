"""Campaign modal selection stays separate from email presentation."""

from __future__ import annotations

import copy
import uuid
from typing import TYPE_CHECKING

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.test import override_settings

from speleodb.campaigns import models
from speleodb.campaigns.forms import DonationCampaignForm
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.tests import EMAIL_TEMPLATE

if TYPE_CHECKING:
    from pathlib import Path


def test_modal_selector_discovers_only_modal_uuid_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    filename = f"{uuid.uuid4()}.html"
    for name in (filename, "notes.html", f"{uuid.uuid1()}.html"):
        (tmp_path / name).write_text("<p>Modal</p>")
    (tmp_path / f"{uuid.uuid4()}.html").mkdir()
    monkeypatch.setattr(models, "MODAL_TEMPLATES_DIR", tmp_path)
    form = DonationCampaignForm()
    assert filename in str(form["modal_template"])
    assert EMAIL_TEMPLATE not in str(form["modal_template"])
    assert filename not in str(form["email_main_template"])
    assert filename not in str(form["reminder_email_template"])
    assert "notes.html" not in str(form["modal_template"])
    field = DonationCampaign._meta.get_field("modal_template")  # noqa: SLF001 - model validation boundary
    assert field.clean(filename, None) == filename
    for invalid in (EMAIL_TEMPLATE, "../email.html", "", "notes.html"):
        with pytest.raises(ValidationError):
            field.clean(invalid, None)
    (tmp_path / filename).unlink()
    with pytest.raises(ValidationError):
        field.clean(filename, None)


def test_dashboard_renders_selected_modal_with_escaped_campaign_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "campaigns" / "modal_templates"
    directory.mkdir(parents=True)
    filename = f"{uuid.uuid4()}.html"
    (directory / filename).write_text(
        '<h2 id="campaign-heading">Selected campaign modal</h2>'
        '<a href="{{ donation_campaign.donation_url }}">'
        "{{ donation_campaign.formatted_goal }}</a>"
    )
    monkeypatch.setattr(models, "MODAL_TEMPLATES_DIR", directory)
    template_settings = copy.deepcopy(settings.TEMPLATES)
    directories = template_settings[0]["DIRS"]
    assert isinstance(directories, list)
    directories.insert(0, tmp_path)
    campaign = DonationCampaign(
        modal_template=filename,
        goal_usd=7200,
        donation_url="https://example.com/give?a=1&b=2",
    )
    with override_settings(TEMPLATES=template_settings):
        html = render_to_string(
            "snippets/donation_campaign.html", {"donation_campaign": campaign}
        )
    assert "Selected campaign modal" in html
    assert "SpeleoDB should stay free..." not in html
    assert "US $7,200" in html
    assert 'href="https://example.com/give?a=1&amp;b=2"' in html
    assert 'id="donation-campaign"' in html
    assert "data-campaign-retry" in html
    campaign.modal_template = "../email.html"
    with pytest.raises(ValueError, match="modal template"):
        render_to_string(
            "snippets/donation_campaign.html", {"donation_campaign": campaign}
        )
