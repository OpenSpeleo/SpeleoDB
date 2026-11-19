from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any
from uuid import uuid4

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django_celery_results.models import TaskResult

from speleodb.campaigns import models
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationCampaignEmail
from speleodb.campaigns.operations import review_digest
from speleodb.campaigns.operations import schedule_campaign
from speleodb.campaigns.operations import snapshot
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import Settings


@pytest.fixture
def reminder_campaign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> DonationCampaign:
    main = f"{uuid4()}.html"
    reminder = f"{uuid4()}.html"
    (tmp_path / main).write_text("<h1>Main appeal</h1>")
    (tmp_path / reminder).write_text("<h1>Reminder appeal</h1>")
    monkeypatch.setattr(models, "EMAIL_TEMPLATES_DIR", tmp_path)
    today = timezone.localdate()
    return DonationCampaign.objects.create(
        email_main_subject="Community appeal",
        email_reminder_subject="Before our campaign closes",
        goal_usd=5000,
        donation_url="https://example.com/give",
        email_main_template=main,
        reminder_email_template=reminder,
        start_date=today,
        end_date=today,
    )


@pytest.mark.django_db
def test_reminder_snapshot_selects_its_distinct_subject(
    reminder_campaign: DonationCampaign,
) -> None:
    reminder_campaign.email_reminder_subject = "Before our campaign closes"
    assert snapshot(reminder_campaign, reminder=True)["subject"] == (
        "Before our campaign closes"
    )


@pytest.mark.django_db
def test_main_and_reminder_delivery_use_their_own_subject_in_headers_and_html(
    reminder_campaign: DonationCampaign,
    django_capture_on_commit_callbacks: Any,
    mailoutbox: Any,
    settings: Settings,
) -> None:
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_STORE_EAGER_RESULT = True
    operator = UserFactory.create(is_staff=True, is_superuser=True)
    for filename in (
        reminder_campaign.email_main_template,
        reminder_campaign.reminder_email_template,
    ):
        (models.EMAIL_TEMPLATES_DIR / filename).write_text(
            "<html><head><title>{{ campaign.subject }}</title></head>"
            "<body><h1>{{ campaign.subject }}</h1></body></html>"
        )
    reminder_campaign.email_main_subject = "Main appeal & discovery"
    reminder_campaign.email_reminder_subject = "Before <our campaign> closes"
    reminder_campaign.save()
    for reminder in (False, True):
        with django_capture_on_commit_callbacks(execute=True):
            schedule_campaign(
                str(reminder_campaign.pk),
                send_id=str(uuid4()),
                requester=operator,
                site_url="https://example.com/",
                digest=review_digest(reminder_campaign, reminder=reminder),
                reminder=reminder,
            )
        reminder_campaign.refresh_from_db()
    assert [message.subject for message in mailoutbox] == [
        "Main appeal & discovery",
        "Before <our campaign> closes",
    ]
    assert "<title>Main appeal &amp; discovery</title>" in (
        mailoutbox[0].alternatives[0].content
    )
    assert "<title>Before &lt;our campaign&gt; closes</title>" in (
        mailoutbox[1].alternatives[0].content
    )
    assert "<h1>Before &lt;our campaign&gt; closes</h1>" in (
        mailoutbox[1].alternatives[0].content
    )
    histories = DonationCampaignEmail.objects.filter(campaign=reminder_campaign)
    assert set(histories.values_list("subject", flat=True)) == {
        reminder_campaign.email_main_subject,
        reminder_campaign.email_reminder_subject,
    }
    assert all(history.recipients == [operator.email] for history in histories)


@pytest.mark.django_db
@pytest.mark.parametrize("page", ["change", "changelist"])
def test_admin_campaign_buttons_open_distinct_send_flows(
    reminder_campaign: DonationCampaign, admin_client: Client, page: str
) -> None:
    detail = reverse(
        "admin:campaigns_donationcampaign_change", args=[reminder_campaign.pk]
    )
    url = (
        detail
        if page == "change"
        else reverse("admin:campaigns_donationcampaign_changelist")
    )
    html = admin_client.get(url).content.decode()
    main_url = reverse("admin:campaign_send", args=[reminder_campaign.pk])
    reminder_url = reverse("admin:campaign_send_reminder", args=[reminder_campaign.pk])
    assert f'action="{main_url}"' in html
    assert f'action="{reminder_url}"' in html
    assert f'form="campaign-send-{reminder_campaign.pk}"' in html
    assert f'form="campaign-send-reminder-{reminder_campaign.pk}"' in html
    assert ">Send Email Campaign</button>" in html
    assert ">Send Reminder Email Campaign</button>" in html


@pytest.mark.django_db
def test_reminder_without_template_is_disabled_and_cannot_queue(
    reminder_campaign: DonationCampaign, admin_client: Client
) -> None:
    reminder_campaign.reminder_email_template = ""
    reminder_campaign.email_reminder_subject = ""
    reminder_campaign.save()
    detail = reverse(
        "admin:campaigns_donationcampaign_change", args=[reminder_campaign.pk]
    )
    html = admin_client.get(detail).content.decode()
    assert "disabled>Send Reminder Email Campaign</button>" in html
    assert "Select and save a reminder email template" in html
    url = reverse("admin:campaign_send_reminder", args=[reminder_campaign.pk])
    for payload in (
        {"action": "review"},
        {"action": "test", "emails": "test@example.com"},
    ):
        response = admin_client.post(url, payload)
        assert response.status_code == HTTPStatus.OK
        assert b"Select and save a reminder email template" in response.content
    assert not TaskResult.objects.exists()
    operator = UserFactory.create(is_superuser=True)
    with pytest.raises(ValueError, match="reminder email template"):
        schedule_campaign(
            str(reminder_campaign.pk),
            requester=operator,
            site_url="https://example.com/",
            reminder=True,
            test_emails=["test@example.com"],
        )
    assert not TaskResult.objects.exists()


@pytest.mark.django_db
def test_reminder_has_independent_review_delivery_and_launch_history(
    reminder_campaign: DonationCampaign,
    django_capture_on_commit_callbacks: Any,
    mailoutbox: Any,
    settings: Settings,
) -> None:
    expected_message_count = 2
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_STORE_EAGER_RESULT = True
    operator = UserFactory.create(is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(operator)
    with django_capture_on_commit_callbacks(execute=True):
        schedule_campaign(
            str(reminder_campaign.pk),
            send_id=str(uuid4()),
            requester=operator,
            site_url="https://example.com/",
            digest=review_digest(reminder_campaign),
        )
    reminder_campaign.refresh_from_db()
    main_history = DonationCampaignEmail.objects.get(
        campaign=reminder_campaign, email_type=DonationCampaignEmail.EmailType.MAIN
    )
    main_recipients = main_history.recipients.copy()
    assert "Main appeal" in mailoutbox[0].alternatives[0].content
    url = reverse("admin:campaign_send_reminder", args=[reminder_campaign.pk])
    review = client.post(url, {"action": "review"})
    assert review.status_code == HTTPStatus.OK
    assert review.context_data is not None
    confirmation = review.context_data["confirmation"]
    assert confirmation
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(url, {"action": "send", "confirmation": confirmation})
    assert response.status_code == HTTPStatus.FOUND
    assert len(mailoutbox) == expected_message_count
    assert "Reminder appeal" in mailoutbox[1].alternatives[0].content
    assert "Main appeal" not in mailoutbox[1].alternatives[0].content
    reminder_campaign.refresh_from_db()
    main_history.refresh_from_db()
    assert main_history.recipients == main_recipients
    reminder_history = DonationCampaignEmail.objects.get(
        campaign=reminder_campaign,
        email_type=DonationCampaignEmail.EmailType.REMINDER,
    )
    assert reminder_history.template == reminder_campaign.reminder_email_template
    assert reminder_history.recipients == [operator.email]
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(url, {"action": "send", "confirmation": confirmation})
    assert b"already submitted" in response.content
    assert len(mailoutbox) == expected_message_count


@pytest.mark.django_db
def test_main_review_cannot_authorize_reminder_and_reminder_tests_do_not_launch(
    reminder_campaign: DonationCampaign,
    admin_client: Client,
) -> None:
    main_url = reverse("admin:campaign_send", args=[reminder_campaign.pk])
    reminder_url = reverse("admin:campaign_send_reminder", args=[reminder_campaign.pk])
    review = admin_client.post(main_url, {"action": "review"})
    assert review.context_data is not None
    response = admin_client.post(
        reminder_url,
        {
            "action": "send",
            "confirmation": review.context_data["confirmation"],
        },
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert not TaskResult.objects.exists()
    response = admin_client.post(
        reminder_url, {"action": "test", "emails": "test@example.com"}
    )
    assert response.status_code == HTTPStatus.FOUND
    task = TaskResult.objects.get()
    assert (
        json.loads(task.task_args)[0]["email_template_source"]
        == "<h1>Reminder appeal</h1>"
    )
    reminder_campaign.refresh_from_db()
    assert not DonationCampaignEmail.objects.exists()


@pytest.mark.django_db
def test_reminder_send_requires_superuser_and_csrf(
    reminder_campaign: DonationCampaign,
) -> None:
    url = reverse("admin:campaign_send_reminder", args=[reminder_campaign.pk])
    client = Client(enforce_csrf_checks=True)
    client.force_login(UserFactory.create(is_staff=True, is_superuser=False))
    assert client.get(url).status_code == HTTPStatus.FORBIDDEN
    client.force_login(UserFactory.create(is_staff=True, is_superuser=True))
    assert client.post(url, {"action": "review"}).status_code == HTTPStatus.FORBIDDEN
    assert (
        client.post(url, {"action": "test", "emails": "test@example.com"}).status_code
        == HTTPStatus.FORBIDDEN
    )
    assert not TaskResult.objects.exists()


@pytest.mark.django_db
def test_reminder_subject_edit_rejects_previously_reviewed_send(
    reminder_campaign: DonationCampaign, admin_client: Client
) -> None:
    url = reverse("admin:campaign_send_reminder", args=[reminder_campaign.pk])
    review = admin_client.post(url, {"action": "review"})
    assert review.context_data is not None
    confirmation = review.context_data["confirmation"]
    original_digest = review_digest(reminder_campaign, reminder=True)
    reminder_campaign.email_reminder_subject = "A revised reminder subject"
    reminder_campaign.save()
    assert review_digest(reminder_campaign, reminder=True) != original_digest
    response = admin_client.post(url, {"action": "send", "confirmation": confirmation})
    assert response.status_code == HTTPStatus.OK
    assert b"changed" in response.content
    assert not TaskResult.objects.exists()
    reminder_campaign.refresh_from_db()
    assert not DonationCampaignEmail.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("email_reminder_subject", ["", "   "])
def test_reminder_snapshot_requires_its_subject(
    reminder_campaign: DonationCampaign,
    email_reminder_subject: str,
) -> None:
    reminder_campaign.email_reminder_subject = email_reminder_subject
    with pytest.raises(ValueError, match="reminder email subject"):
        snapshot(reminder_campaign, reminder=True)
    assert not TaskResult.objects.exists()
