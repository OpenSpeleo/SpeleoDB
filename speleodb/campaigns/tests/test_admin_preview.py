from __future__ import annotations

import json
from datetime import timedelta
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
from speleodb.campaigns.models import DEFAULT_MODAL_TEMPLATE
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationCampaignEmail
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import Settings


HISTORY_INLINE_FORM_DATA = {
    "donationcampaignemail_set-TOTAL_FORMS": "0",
    "donationcampaignemail_set-INITIAL_FORMS": "0",
    "donationcampaignemail_set-MIN_NUM_FORMS": "0",
    "donationcampaignemail_set-MAX_NUM_FORMS": "0",
}


@pytest.fixture
def template_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    main = f"{uuid4()}.html"
    reminder = f"{uuid4()}.html"
    (tmp_path / main).write_text("<h1>Main preview: {{ campaign.subject }}</h1>")
    (tmp_path / reminder).write_text(
        "<h1>Reminder preview: {{ campaign.subject }}</h1>"
    )
    monkeypatch.setattr(models, "EMAIL_TEMPLATES_DIR", tmp_path)
    return main, reminder


@pytest.fixture
def campaign_data(template_names: tuple[str, str]) -> dict[str, str]:
    today = timezone.localdate()
    return {
        "email_main_subject": "Current appeal",
        "email_reminder_subject": "Reminder appeal",
        "goal_usd": "5000",
        "donors": "",
        "donation_url": "https://example.com/give",
        "start_date": str(today),
        "end_date": str(today + timedelta(days=30)),
        "reminder_days": "7",
        "email_main_template": template_names[0],
        "modal_template": DEFAULT_MODAL_TEMPLATE,
        "reminder_email_template": template_names[1],
    }


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["email_main_template", "reminder_email_template"])
def test_save_preview_persists_form_and_sends_only_to_current_admin(
    campaign_data: dict[str, str],
    field: str,
    mailoutbox: Any,
    django_capture_on_commit_callbacks: Any,
    settings: Settings,
) -> None:
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_STORE_EAGER_RESULT = True
    campaign = DonationCampaign.objects.create(
        **{k: v for k, v in campaign_data.items() if k != "donors"}
    )
    history = DonationCampaignEmail.objects.create(
        campaign=campaign,
        email_type=DonationCampaignEmail.EmailType.MAIN,
        subject="Previously sent appeal",
        recipients=["past@example.com"],
        template=campaign.email_main_template,
    )
    previous_history = DonationCampaignEmail.objects.values().get(pk=history.pk)
    operator = UserFactory.create(
        is_superuser=True, is_staff=True, email_on_speleodb_updates=False
    )
    UserFactory.create()
    client = Client()
    client.force_login(operator)
    url = reverse("admin:campaigns_donationcampaign_change", args=[campaign.pk])
    campaign_data.update(
        email_main_subject="Updated <discovery>",
        email_reminder_subject="Reminder <discovery>",
        goal_usd="7200",
    )
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            url,
            {
                **HISTORY_INLINE_FORM_DATA,
                **campaign_data,
                "_save_preview": field,
                "emails": "somebody-else@example.com",
            },
        )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert operator.email in data["message"]
    assert data["change_url"] == url
    assert data["task_results_url"]
    campaign.refresh_from_db()
    assert campaign.email_main_subject == "Updated <discovery>"
    assert campaign.email_reminder_subject == "Reminder <discovery>"
    assert campaign.goal_usd == int(campaign_data["goal_usd"])
    assert DonationCampaignEmail.objects.values().get(pk=history.pk) == previous_history
    assert [message.to for message in mailoutbox] == [[operator.email]]
    expected_subject = (
        campaign_data["email_reminder_subject"]
        if field == "reminder_email_template"
        else campaign_data["email_main_subject"]
    )
    assert mailoutbox[0].subject == expected_subject
    expected = (
        "Reminder preview" if field == "reminder_email_template" else "Main preview"
    )
    assert expected in mailoutbox[0].alternatives[0].content
    escaped_subject = (
        "Reminder &lt;discovery&gt;"
        if field == "reminder_email_template"
        else "Updated &lt;discovery&gt;"
    )
    assert escaped_subject in mailoutbox[0].alternatives[0].content
    task = TaskResult.objects.get()
    args = json.loads(task.task_args)
    assert args[3] is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalid_field",
    [
        "email_main_subject",
        "email_reminder_subject",
        "goal_usd",
        "email_main_template",
        "reminder_email_template",
        "end_date",
    ],
)
def test_invalid_preview_form_preserves_campaign_and_creates_no_tasks(
    campaign_data: dict[str, str],
    invalid_field: str,
    admin_client: Client,
) -> None:
    campaign = DonationCampaign.objects.create(
        **{k: v for k, v in campaign_data.items() if k != "donors"}
    )
    url = reverse("admin:campaigns_donationcampaign_change", args=[campaign.pk])
    invalid = {
        "email_main_subject": "",
        "email_reminder_subject": "",
        "goal_usd": "invalid",
        "email_main_template": "missing.html",
        "reminder_email_template": "",
        "end_date": "2000-01-01",
    }
    response = admin_client.post(
        url,
        {
            **HISTORY_INLINE_FORM_DATA,
            **campaign_data,
            "email_main_subject": "Do not persist",
            invalid_field: invalid[invalid_field],
            "_save_preview": "reminder_email_template",
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    error_field = "__all__" if invalid_field == "end_date" else invalid_field
    assert error_field in response.json()["errors"]
    campaign.refresh_from_db()
    assert campaign.email_main_subject == "Current appeal"
    assert not TaskResult.objects.exists()


@pytest.mark.django_db
def test_preview_requires_active_superuser_and_csrf(
    campaign_data: dict[str, str],
) -> None:
    campaign = DonationCampaign.objects.create(
        **{k: v for k, v in campaign_data.items() if k != "donors"}
    )
    url = reverse("admin:campaigns_donationcampaign_change", args=[campaign.pk])
    client = Client()
    client.force_login(UserFactory.create(is_staff=True, is_superuser=False))
    data = {
        **HISTORY_INLINE_FORM_DATA,
        **campaign_data,
        "_save_preview": "email_main_template",
        "email_main_subject": "Do not persist",
    }
    assert client.post(url, data).status_code == HTTPStatus.FORBIDDEN
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(UserFactory.create(is_staff=True, is_superuser=True))
    assert csrf_client.post(url, data).status_code == HTTPStatus.FORBIDDEN
    campaign.refresh_from_db()
    assert campaign.email_main_subject == "Current appeal"
    assert not TaskResult.objects.exists()


@pytest.mark.django_db
def test_preview_rejects_admin_without_email_before_saving(
    campaign_data: dict[str, str],
) -> None:
    campaign = DonationCampaign.objects.create(
        **{k: v for k, v in campaign_data.items() if k != "donors"}
    )
    client = Client()
    client.force_login(UserFactory.create(is_staff=True, is_superuser=True, email=""))
    response = client.post(
        reverse("admin:campaigns_donationcampaign_change", args=[campaign.pk]),
        {
            **HISTORY_INLINE_FORM_DATA,
            **campaign_data,
            "email_main_subject": "Do not persist",
            "_save_preview": "email_main_template",
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "email" in response.json()["message"].lower()
    campaign.refresh_from_db()
    assert campaign.email_main_subject == "Current appeal"
    assert not TaskResult.objects.exists()


@pytest.mark.django_db
def test_preview_can_create_campaign_once_then_use_change_url(
    campaign_data: dict[str, str],
    admin_client: Client,
) -> None:
    response = admin_client.post(
        reverse("admin:campaigns_donationcampaign_add"),
        {
            **HISTORY_INLINE_FORM_DATA,
            **campaign_data,
            "_save_preview": "email_main_template",
        },
    )
    assert response.status_code == HTTPStatus.OK
    campaign = DonationCampaign.objects.get()
    url = reverse("admin:campaigns_donationcampaign_change", args=[campaign.pk])
    assert response.json()["change_url"] == url
    response = admin_client.post(
        url,
        {
            **HISTORY_INLINE_FORM_DATA,
            **campaign_data,
            "_save_preview": "reminder_email_template",
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert DonationCampaign.objects.count() == 1
    expected_previews = 2
    assert TaskResult.objects.count() == expected_previews


@pytest.mark.django_db
def test_template_fields_render_adjacent_preview_controls(
    campaign_data: dict[str, str], admin_client: Client
) -> None:
    campaign = DonationCampaign.objects.create(
        **{k: v for k, v in campaign_data.items() if k != "donors"}
    )
    response = admin_client.get(
        reverse("admin:campaigns_donationcampaign_change", args=[campaign.pk])
    )
    html = response.content.decode()
    template_fields = ("email_main_template", "reminder_email_template")
    for field in template_fields:
        assert f'data-campaign-save-preview="{field}"' in html
        assert f'data-campaign-preview-status="{field}"' in html
    assert 'name="modal_template"' in html
    assert 'data-campaign-save-preview="modal_template"' not in html
    assert html.count('class="campaign-template-controls"') == len(template_fields)
    assert "data-campaign-preview-dialog" in html
    assert "data-campaign-preview-close" in html
    assert 'data-speleodb-controller="admin-campaign-preview"' in html


@pytest.mark.django_db
def test_main_preview_allows_no_email_reminder_subject_without_reminder_template(
    campaign_data: dict[str, str], admin_client: Client
) -> None:
    campaign_data.update(reminder_email_template="", email_reminder_subject="")
    campaign = DonationCampaign.objects.create(
        **{k: v for k, v in campaign_data.items() if k != "donors"}
    )
    response = admin_client.post(
        reverse("admin:campaigns_donationcampaign_change", args=[campaign.pk]),
        {
            **HISTORY_INLINE_FORM_DATA,
            **campaign_data,
            "email_main_subject": "Saved main subject",
            "_save_preview": "email_main_template",
        },
    )
    assert response.status_code == HTTPStatus.OK
    campaign.refresh_from_db()
    assert campaign.email_main_subject == "Saved main subject"
    assert campaign.email_reminder_subject == ""
    assert campaign.reminder_email_template == ""
    assert TaskResult.objects.count() == 1


@pytest.mark.django_db
def test_admin_groups_each_email_with_its_subject_template_and_send_action(
    campaign_data: dict[str, str], admin_client: Client
) -> None:
    campaign = DonationCampaign.objects.create(
        **{k: v for k, v in campaign_data.items() if k != "donors"}
    )
    response = admin_client.get(
        reverse("admin:campaigns_donationcampaign_change", args=[campaign.pk])
    )
    assert response.context_data is not None
    sections = {
        fieldset.name: fieldset.fields
        for fieldset in response.context_data["adminform"]
    }
    assert sections["Main email"] == (
        "email_main_subject",
        "email_main_template",
        "send_email",
    )
    assert sections["Reminder email"] == (
        "email_reminder_subject",
        "reminder_email_template",
        "send_reminder_email",
    )
