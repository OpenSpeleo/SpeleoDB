"""Campaign boundaries: reviewed sends, isolation, delivery and preferences."""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any
from uuid import uuid4

import pytest
from celery import current_app
from celery.app.trace import build_tracer
from django.db import transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django_celery_results.models import TaskResult

from speleodb.campaigns import forms
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationCampaignEmail
from speleodb.campaigns.models import email_template_choices
from speleodb.campaigns.operations import audience
from speleodb.campaigns.operations import review_digest
from speleodb.campaigns.operations import schedule_campaign
from speleodb.campaigns.operations import snapshot
from speleodb.campaigns.tasks import send_campaign_email
from speleodb.common.enums import TaskResultStatus
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings


@pytest.fixture
def campaign() -> DonationCampaign:
    today = timezone.localdate()
    return DonationCampaign.objects.create(
        email_main_template=email_template_choices()[0][0],
        email_main_subject="Support <exploration>",
        goal_usd=5000,
        donation_url="https://www.paypal.com/donate",
        start_date=today,
        end_date=today,
    )


@pytest.mark.django_db
def test_test_recipient_validation_and_isolation(campaign: DonationCampaign) -> None:
    requester = UserFactory.create(is_superuser=True)
    form = forms.TestEmailForm(
        {"emails": "hello@example.com, HELLO@example.com\nsecond@example.com"}
    )
    assert form.is_valid()
    receipt = schedule_campaign(
        str(campaign.pk),
        requester=requester,
        site_url="https://speleodb.org/",
        test_emails=form.cleaned_data["emails"],
    )
    rows = list(TaskResult.objects.filter(task_id__in=receipt.task_ids))
    assert {json.loads(row.task_args)[1] for row in rows} == {
        "hello@example.com",
        "second@example.com",
    }
    assert all(json.loads(row.task_args)[3] is None for row in rows)
    assert all(json.loads(row.meta)["user_id"] is None for row in rows)
    assert all(
        json.loads(row.meta)["site_url"] == "https://speleodb.org/" for row in rows
    )
    campaign.refresh_from_db()
    assert not DonationCampaignEmail.objects.exists()
    assert not forms.TestEmailForm({"emails": "bad-address"}).is_valid()


@pytest.mark.django_db
def test_review_change_and_replayed_submission_are_rejected(
    campaign: DonationCampaign,
) -> None:
    requester = UserFactory.create(is_superuser=True)
    digest = review_digest(campaign)
    user = UserFactory.create()
    with pytest.raises(ValueError, match="changed"):
        schedule_campaign(
            str(campaign.pk),
            send_id=str(uuid4()),
            requester=requester,
            site_url="https://speleodb.org/",
            digest=digest,
        )
    user.email_on_speleodb_updates = False
    user.save()
    send_id = str(uuid4())
    receipt = schedule_campaign(
        str(campaign.pk),
        send_id=send_id,
        requester=requester,
        site_url="https://speleodb.org/",
        digest=review_digest(campaign),
    )
    assert receipt.task_ids
    campaign.refresh_from_db()
    assert not DonationCampaignEmail.objects.exists()
    with pytest.raises(ValueError, match="already"):
        schedule_campaign(
            str(campaign.pk),
            send_id=send_id,
            requester=requester,
            site_url="https://speleodb.org/",
            digest=review_digest(campaign),
        )
    assert all(recipient["user_id"] != str(user.pk) for recipient in audience(campaign))
    repeat = schedule_campaign(
        str(campaign.pk),
        send_id=str(uuid4()),
        requester=requester,
        site_url="https://speleodb.org/",
        digest=review_digest(campaign),
    )
    assert repeat.group_id != receipt.group_id


@pytest.mark.django_db
def test_delivery_is_single_execution_and_preferences_rechecked(
    campaign: DonationCampaign, mailoutbox: Any
) -> None:
    requester = UserFactory.create(is_superuser=True)
    receipt = schedule_campaign(
        str(campaign.pk),
        send_id=str(uuid4()),
        requester=requester,
        site_url="https://speleodb.org/",
        digest=review_digest(campaign),
    )
    row = TaskResult.objects.get(task_id=receipt.task_ids[0])
    args = json.loads(row.task_args)
    assert json.loads(row.meta)["user_id"] == args[3]
    assert json.loads(row.meta)["site_url"] == args[2]
    send_campaign_email.apply(args=args, task_id=row.task_id, throw=True)
    send_campaign_email.apply(args=args, task_id=row.task_id, throw=True)
    assert len(mailoutbox) == 1
    message = mailoutbox[0]
    assert "List-Unsubscribe" not in message.extra_headers
    assert "List-Unsubscribe-Post" not in message.extra_headers
    assert (
        'href="https://speleodb.org/private/preferences/"'
        in message.alternatives[0].content
    )
    assert "Support &lt;exploration&gt;" in message.alternatives[0].content
    row.refresh_from_db()
    assert row.status == TaskResultStatus.SUCCESS
    assert receipt.group_id is not None
    history = DonationCampaignEmail.objects.get(pk=receipt.group_id)
    assert history.recipients == message.to
    assert history.subject == campaign.email_main_subject


@pytest.mark.django_db
def test_opt_out_after_submission_skips_delivery(
    campaign: DonationCampaign, mailoutbox: Any
) -> None:
    requester = UserFactory.create(is_superuser=True)
    receipt = schedule_campaign(
        str(campaign.pk),
        send_id=str(uuid4()),
        requester=requester,
        site_url="https://speleodb.org/",
        digest=review_digest(campaign),
    )
    requester.email_on_speleodb_updates = False
    requester.save()
    row = TaskResult.objects.get(task_id=receipt.task_ids[0])
    send_campaign_email.apply(
        args=json.loads(row.task_args), task_id=row.task_id, throw=True
    )
    row.refresh_from_db()
    assert json.loads(row.result)["outcome"] == "skipped"
    assert not mailoutbox
    assert not DonationCampaignEmail.objects.exists()


@pytest.mark.django_db
def test_admin_review_send_opens_native_task_result(
    campaign: DonationCampaign,
    django_capture_on_commit_callbacks: Any,
    mailoutbox: Any,
    settings: Settings,
) -> None:
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_STORE_EAGER_RESULT = True
    client = Client()
    operator = UserFactory.create(is_superuser=True, is_staff=True)
    url = reverse("admin:campaign_send", args=[campaign.pk])
    client.force_login(
        UserFactory.create(is_staff=True, email_on_speleodb_updates=False)
    )
    assert client.get(url).status_code == HTTPStatus.FORBIDDEN
    client.force_login(operator)
    assert client.get(url).status_code == HTTPStatus.OK
    assert not TaskResult.objects.exists()
    review = client.post(url, {"action": "review"})
    assert review.status_code == HTTPStatus.OK
    assert not TaskResult.objects.exists()
    assert review.context_data is not None
    confirmation = review.context_data["confirmation"]
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(url, {"action": "send", "confirmation": confirmation})
    assert response.status_code == HTTPStatus.FOUND
    campaign.refresh_from_db()
    result = TaskResult.objects.get(
        task_name="speleodb.campaigns.tasks.send_campaign_email"
    )
    result_url = reverse(
        "admin:django_celery_results_taskresult_change", args=[result.pk]
    )
    assert response["Location"] == result_url
    assert mailoutbox
    receipt = client.get(response["Location"])
    assert receipt.status_code == HTTPStatus.OK
    assert b"backend-accepted" in receipt.content
    history = DonationCampaignEmail.objects.get(campaign=campaign)
    history_url = reverse(
        "admin:campaigns_donationcampaignemail_change", args=[history.pk]
    )
    assert result_url.encode() in client.get(history_url).content
    count = len(mailoutbox)
    with django_capture_on_commit_callbacks(execute=True):
        client.post(url, {"action": "send", "confirmation": confirmation})
    assert len(mailoutbox) == count
    secure_client = Client(enforce_csrf_checks=True)
    secure_client.force_login(operator)
    assert (
        secure_client.post(
            url, {"action": "test", "emails": "test@example.com"}
        ).status_code
        == HTTPStatus.FORBIDDEN
    )


@pytest.mark.django_db
@pytest.mark.parametrize("reminder", [False, True])
def test_rollback_does_not_publish_or_keep_send_history(
    campaign: DonationCampaign,
    django_capture_on_commit_callbacks: Any,
    reminder: bool,
) -> None:
    campaign.reminder_email_template = campaign.email_main_template
    campaign.email_reminder_subject = "Before this campaign closes"
    campaign.save()
    operator = UserFactory.create(is_superuser=True)
    with (
        django_capture_on_commit_callbacks(execute=True) as callbacks,
        transaction.atomic(),
    ):
        schedule_campaign(
            str(campaign.pk),
            send_id=str(uuid4()),
            requester=operator,
            site_url="https://speleodb.org/",
            digest=review_digest(campaign, reminder=reminder),
            reminder=reminder,
        )
        transaction.set_rollback(True)
    campaign.refresh_from_db()
    assert not DonationCampaignEmail.objects.exists()
    assert not TaskResult.objects.exists()
    assert not callbacks


@pytest.mark.django_db
def test_delivery_failure_preserves_exception_and_does_not_block_other_recipient(
    campaign: DonationCampaign,
    mailoutbox: Any,
) -> None:
    operator = UserFactory.create(is_superuser=True)
    receipt = schedule_campaign(
        str(campaign.pk),
        requester=operator,
        site_url="https://speleodb.org/",
        test_emails=["first@example.com", "second@example.com"],
    )
    first, second = [
        TaskResult.objects.get(task_id=value) for value in receipt.task_ids
    ]
    args = json.loads(first.task_args)
    args[0]["subject"] = "Invalid\nHeader"
    with pytest.raises(ValueError, match="linefeed"):
        send_campaign_email.apply(args=args, task_id=first.task_id, throw=True)
    first.refresh_from_db()
    assert first.status == TaskResultStatus.FAILURE
    error = current_app.AsyncResult(first.task_id).result
    assert isinstance(error, ValueError)
    send_campaign_email.apply(
        args=json.loads(second.task_args), task_id=second.task_id, throw=True
    )
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["second@example.com"]


@pytest.mark.django_db
def test_audience_keeps_inactive_accounts_but_excludes_opt_outs(
    campaign: DonationCampaign,
) -> None:
    inactive = UserFactory.create(is_active=False)
    opted_out = UserFactory.create(email_on_speleodb_updates=False)
    assert {row["user_id"] for row in audience(campaign)} == {str(inactive.pk)}
    assert str(opted_out.pk) not in {row["user_id"] for row in audience(campaign)}


@pytest.mark.django_db(transaction=True)
def test_worker_trace_sends_campaign_email_and_records_acceptance(
    campaign: DonationCampaign, mailoutbox: Any
) -> None:
    task_id = str(uuid4())
    task_name = "speleodb.campaigns.tasks.send_campaign_email"
    content = snapshot(campaign)
    args = [content, "preview@example.com", "https://speleodb.org/", None]
    TaskResult.objects.create(
        task_id=task_id,
        task_name=task_name,
        status=TaskResultStatus.PENDING,
        task_args=json.dumps(args),
        task_kwargs="{}",
        content_type="application/json",
        content_encoding="utf-8",
        meta=json.dumps({"operation": "campaign", "is_test": True, "time_limit": 120}),
    )
    # Exercise Celery's worker trace: eager apply() omits automatic STARTED writes.
    trace = build_tracer(task_name, send_campaign_email, app=current_app, eager=False)
    trace(task_id, args, {}, {"id": task_id, "task": task_name})
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["preview@example.com"]
    assert mailoutbox[0].subject == campaign.email_main_subject
    result = TaskResult.objects.get(task_id=task_id)
    assert result.status == TaskResultStatus.SUCCESS
    assert json.loads(result.result)["outcome"] == "backend-accepted"
    campaign.refresh_from_db()
    assert not DonationCampaignEmail.objects.exists()


@pytest.mark.django_db
def test_send_page_has_delivery_controls_without_previews(
    campaign: DonationCampaign, admin_client: Client
) -> None:
    response = admin_client.get(reverse("admin:campaign_send", args=[campaign.pk]))
    assert response.status_code == HTTPStatus.OK
    html = response.content.decode()
    assert "Send test email" in html
    assert "Review send" in html
    assert "<iframe" not in html
    assert "Email preview" not in html
    assert "popup-preview" not in html


@pytest.mark.django_db
@pytest.mark.parametrize(
    "recipients", [["one@example.com"], ["one@example.com", "two@example.com"]]
)
def test_test_send_opens_only_its_native_task_results(
    campaign: DonationCampaign, admin_client: Client, recipients: list[str]
) -> None:
    unrelated = TaskResult.objects.create(
        task_id=str(uuid4()), status=TaskResultStatus.PENDING
    )
    response = admin_client.post(
        reverse("admin:campaign_send", args=[campaign.pk]),
        {"action": "test", "emails": ",".join(recipients)},
    )
    assert response.status_code == HTTPStatus.FOUND
    results = TaskResult.objects.exclude(pk=unrelated.pk)
    if len(recipients) == 1:
        assert response["Location"] == reverse(
            "admin:django_celery_results_taskresult_change", args=[results.get().pk]
        )
    else:
        assert response["Location"].startswith(
            reverse("admin:django_celery_results_taskresult_changelist") + "?"
        )
        page = admin_client.get(response["Location"])
        assert page.status_code == HTTPStatus.OK
        assert page.context_data is not None
        assert set(
            page.context_data["cl"].queryset.values_list("pk", flat=True)
        ) == set(results.values_list("pk", flat=True))


@pytest.mark.django_db(transaction=True)
def test_duplicate_worker_delivery_preserves_original_failure(
    campaign: DonationCampaign, mailoutbox: Any
) -> None:
    task_id = str(uuid4())
    task_name = "speleodb.campaigns.tasks.send_campaign_email"
    content = snapshot(campaign)
    content["subject"] = "Invalid\nHeader"
    args = [content, "preview@example.com", "https://speleodb.org/", None]
    row = TaskResult.objects.create(
        task_id=task_id,
        task_name=task_name,
        status=TaskResultStatus.PENDING,
        meta=json.dumps({"operation": "campaign", "is_test": True, "time_limit": 120}),
    )
    trace = build_tracer(task_name, send_campaign_email, app=current_app, eager=False)
    request = {"id": task_id, "task": task_name}
    trace(task_id, args, {}, request)
    row.refresh_from_db()
    assert row.status == TaskResultStatus.FAILURE
    original_result = row.result
    original_traceback = row.traceback
    assert original_traceback
    trace(task_id, args, {}, request)
    row.refresh_from_db()
    assert row.status == TaskResultStatus.FAILURE
    assert row.result == original_result
    assert row.traceback == original_traceback
    assert isinstance(current_app.AsyncResult(task_id).result, ValueError)
    assert not mailoutbox


@pytest.mark.django_db(transaction=True)
def test_duplicate_worker_delivery_does_not_complete_running_task(
    campaign: DonationCampaign, mailoutbox: Any
) -> None:
    task_id = str(uuid4())
    task_name = "speleodb.campaigns.tasks.send_campaign_email"
    row = TaskResult.objects.create(
        task_id=task_id,
        task_name=task_name,
        status=TaskResultStatus.STARTED,
        meta=json.dumps({"operation": "campaign", "is_test": True, "stage": "sending"}),
    )
    trace = build_tracer(task_name, send_campaign_email, app=current_app, eager=False)
    trace(
        task_id,
        [snapshot(campaign), "preview@example.com", "https://speleodb.org/", None],
        {},
        {"id": task_id, "task": task_name},
    )
    row.refresh_from_db()
    assert row.status == TaskResultStatus.STARTED
    assert json.loads(row.meta)["stage"] == "sending"
    assert not mailoutbox


@pytest.mark.django_db
def test_send_page_survives_expired_task_group(
    campaign: DonationCampaign, admin_client: Client
) -> None:
    operator = UserFactory.create(is_staff=True, is_superuser=True)
    receipt = schedule_campaign(
        str(campaign.pk),
        send_id=str(uuid4()),
        requester=operator,
        site_url="https://speleodb.org/",
        digest=review_digest(campaign),
    )
    assert receipt.group_id is not None
    current_app.backend.delete_group(receipt.group_id)
    response = admin_client.get(reverse("admin:campaign_send", args=[campaign.pk]))
    assert response.status_code == HTTPStatus.OK
    assert b"Full-audience resend is disabled" not in response.content
    assert b"View task results" not in response.content
    assert b"Review send" in response.content
    campaign.refresh_from_db()
    assert not DonationCampaignEmail.objects.exists()
