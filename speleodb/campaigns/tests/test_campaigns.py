from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationCampaignDismissal
from speleodb.campaigns.models import email_template_choices
from speleodb.users.tests.factories import UserFactory


@pytest.mark.django_db
def test_dismissal_survives_campaign_rescheduling() -> None:
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        email_main_template=email_template_choices()[0][0],
        email_main_subject="Support SpeleoDB",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today,
        end_date=today,
    )
    user = UserFactory.create()
    DonationCampaignDismissal.objects.get_or_create(campaign=campaign, user=user)
    campaign.start_date = today + timedelta(days=1)
    campaign.end_date = today + timedelta(days=2)
    campaign.save()
    campaign.start_date = today
    campaign.save()
    assert not campaign.should_invite(user)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("start_offset", "end_offset", "expected"),
    [(1, 2, False), (-2, -1, False), (0, 0, True), (-1, 0, True), (0, 1, True)],
)
def test_campaign_invitation_date_window(
    start_offset: int, end_offset: int, expected: bool
) -> None:
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        email_main_template=email_template_choices()[0][0],
        email_main_subject="Support SpeleoDB",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today + timedelta(days=start_offset),
        end_date=today + timedelta(days=end_offset),
    )
    user = UserFactory.create()
    assert campaign.should_invite(user) is expected


@pytest.mark.django_db
def test_campaign_rejects_reversed_dates() -> None:
    today = timezone.localdate()
    campaign = DonationCampaign(
        email_main_template=email_template_choices()[0][0],
        email_main_subject="Support SpeleoDB",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today,
        end_date=today - timedelta(days=1),
    )
    with pytest.raises(ValidationError):
        campaign.full_clean()


@pytest.mark.django_db
def test_dismiss_endpoint_is_account_scoped_and_keeps_one_record() -> None:
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        email_main_template=email_template_choices()[0][0],
        email_main_subject="Support",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today,
        end_date=today,
    )
    user = UserFactory.create()
    other = UserFactory.create()
    client = APIClient()
    url = f"/api/v2/user/donation-campaigns/{campaign.pk}/dismiss/"
    assert client.post(url).status_code in {401, 403}
    client.force_authenticate(user)
    assert client.post(url).status_code == HTTPStatus.NO_CONTENT
    assert client.post(url).status_code == HTTPStatus.NO_CONTENT
    assert (
        DonationCampaignDismissal.objects.filter(campaign=campaign, user=user).count()
        == 1
    )
    assert campaign.should_invite(other)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("days_ago", "campaign_offset", "expected"),
    [(6, 0, False), (8, 0, True), (8, -1, False), (8, 1, False)],
)
def test_weekly_reminder_requires_elapsed_week_and_active_campaign(
    days_ago: int, campaign_offset: int, expected: bool
) -> None:
    day = timezone.localdate() + timedelta(days=campaign_offset)
    campaign = DonationCampaign.objects.create(
        email_main_template=email_template_choices()[0][0],
        email_main_subject="Support",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=day,
        end_date=day,
    )
    user = UserFactory.create()
    dismissal = DonationCampaignDismissal.objects.create(campaign=campaign, user=user)
    DonationCampaignDismissal.objects.filter(pk=dismissal.pk).update(
        modified_date=timezone.now() - timedelta(days=days_ago)
    )
    assert campaign.should_invite(user) is expected
    if expected:
        client = APIClient()
        client.force_authenticate(user)
        assert (
            client.post(
                f"/api/v2/user/donation-campaigns/{campaign.pk}/dismiss/"
            ).status_code
            == HTTPStatus.NO_CONTENT
        )
        assert not campaign.should_invite(user)
        assert (
            DonationCampaignDismissal.objects.filter(
                campaign=campaign, user=user
            ).count()
            == 1
        )


@pytest.mark.django_db
def test_reminder_interval_comes_from_campaign() -> None:
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        email_main_template=email_template_choices()[0][0],
        email_main_subject="Support",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today,
        end_date=today,
        reminder_days=14,
    )
    user = UserFactory.create()
    dismissal = DonationCampaignDismissal.objects.create(campaign=campaign, user=user)
    DonationCampaignDismissal.objects.filter(pk=dismissal.pk).update(
        modified_date=timezone.now() - timedelta(days=8)
    )
    assert not campaign.should_invite(user)
    campaign.reminder_days = 7
    campaign.save()
    assert campaign.should_invite(user)
