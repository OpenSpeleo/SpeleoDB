from typing import Any

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.utils import timezone

from speleodb.campaigns.models import DEFAULT_MODAL_TEMPLATE
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import email_template_choices
from speleodb.users.tests.factories import UserFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            " First@Example.com \n\nfirst@example.com\nsecond@example.com",
            ["first@example.com", "second@example.com"],
        ),
        ("", []),
    ],
)
def test_admin_donors_accept_one_address_per_line(
    value: str, expected: list[str]
) -> None:
    request = RequestFactory().get("/")
    request.user = UserFactory.create(is_staff=True, is_superuser=True)
    form_class = admin.site._registry[DonationCampaign].get_form(request)  # noqa: SLF001
    today = timezone.localdate()
    data: dict[str, Any] = {
        "email_main_subject": "Community appeal",
        "email_main_template": email_template_choices()[0][0],
        "modal_template": DEFAULT_MODAL_TEMPLATE,
        "goal_usd": 5000,
        "donation_url": "https://example.com/give",
        "start_date": today,
        "end_date": today,
        "reminder_days": 7,
        "donors": value,
    }
    form = form_class(data=data)
    assert form.is_valid(), form.errors
    campaign = form.save()
    campaign.refresh_from_db()
    assert campaign.donors == expected
    rendered = form_class(instance=campaign)["donors"].value()
    assert rendered == "\n".join(expected)
    data["donors"] = "not-an-email"
    invalid = form_class(data=data, instance=campaign)
    assert not invalid.is_valid()
    assert "donors" in invalid.errors
    campaign.refresh_from_db()
    assert campaign.donors == expected
