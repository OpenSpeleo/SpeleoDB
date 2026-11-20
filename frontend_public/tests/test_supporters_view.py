from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains
from pytest_django.asserts import assertNotContains

from frontend_public.models import PersonSupporter
from speleodb.campaigns.letter_rendering import example_letter
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationThankYouTemplate

if TYPE_CHECKING:
    from django.test import Client
    from pytest_django.fixtures import Settings


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("destination", "shows_donation"),
    [
        ("", False),
        ("   ", False),
        ("give.example.org/speleodb", False),
        ("http://example.org/give", False),
        (" https://example.org/give ", True),
    ],
)
def test_anonymous_donation_section(
    client: Client, settings: Settings, destination: str, *, shows_donation: bool
) -> None:
    settings.SPELEODB_DONATION_CAMPAIGN_URL = destination
    response = client.get(reverse("supporters"))
    assertContains(response, "To everyone who supports SpeleoDB, thank you.")
    if shows_donation:
        assertContains(response, "Donate to SpeleoDB")
        assertContains(response, destination.strip())
    else:
        assertNotContains(response, "Donate to SpeleoDB")


@pytest.mark.django_db
def test_private_gift_and_campaign_records_do_not_populate_public_credits(
    client: Client, settings: Settings
) -> None:
    settings.SPELEODB_DONATION_CAMPAIGN_URL = ""
    template = DonationThankYouTemplate.objects.create(
        name="Acknowledgment", email_subject="Thank you"
    )
    letter = example_letter(template)
    letter.save()
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        start_date=today,
        end_date=today,
        goal_usd=100,
        donors=["unpublished@example.org"],
        donation_url="https://example.org/private-campaign",
    )

    response = client.get(reverse("supporters"))
    assert response.status_code == HTTPStatus.OK
    html = response.content.decode()
    assert letter.donor_name not in html
    assert letter.donor_email not in html
    assert campaign.donors[0] not in html
    assert campaign.donation_url not in html


@pytest.mark.django_db
def test_page_renders_people_alphabetically_by_display_name(client: Client) -> None:
    PersonSupporter.objects.bulk_create(
        [
            PersonSupporter(name="Zoe Surveyor"),
            PersonSupporter(name="ada Explorer"),
            PersonSupporter(
                name="Lee Surveyor", order=1, website="https://example.org/lee"
            ),
        ]
    )
    response = client.get(reverse("supporters"))
    assert response.status_code == HTTPStatus.OK
    html = response.content.decode()
    assert (
        html.index("ada Explorer")
        < html.index("Lee Surveyor")
        < html.index("Zoe Surveyor")
    )
