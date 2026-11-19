"""A confirmed gift produces one archived letter and one matching attachment."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from typing import Any

import pymupdf
import pytest
from celery import current_app
from celery.app.trace import build_tracer
from django.core.mail.exceptions import InvalidMailer
from django.template import TemplateSyntaxError
from django.test import override_settings
from django_celery_results.models import TaskResult

from speleodb.campaigns import letter_operations
from speleodb.campaigns.models import DonationThankYouLetters
from speleodb.campaigns.models import DonationThankYouTemplate
from speleodb.common.enums import TaskResultStatus
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from pytest_django.fixtures import Settings

SITE_URL = "https://speleodb.example/"


@pytest.fixture
def gift() -> Iterator[DonationThankYouLetters]:
    template = DonationThankYouTemplate.objects.create(
        name="Test thank you", email_subject="Your gift acknowledgment"
    )
    letter = DonationThankYouLetters.objects.create(
        template=template,
        donor_name="Alex & Chris",
        donor_email="gift@example.org",
        amount=Decimal("425.50"),
        gift_date=date(2026, 1, 12),
        payment_method="Wire transfer",
        transaction_reference="wire-042",
    )
    yield letter
    for archived in DonationThankYouLetters.objects.filter(template=template).exclude(
        pdf=""
    ):
        archived.pdf.delete(save=False)


def deliver(task_id: str) -> TaskResult:
    row = TaskResult.objects.get(task_id=task_id)
    current_app.autodiscover_tasks(force=True)
    current_app.tasks[row.task_name].apply(
        task_id=task_id,
        args=json.loads(row.task_args),
        kwargs=json.loads(row.task_kwargs),
        throw=True,
    )
    row.refresh_from_db()
    return row


@pytest.mark.django_db(transaction=True)
def test_issue_and_resend_deliver_archived_bytes(
    gift: DonationThankYouLetters, mailoutbox: Any
) -> None:
    operator = UserFactory.create(is_superuser=True)
    task_id = letter_operations.issue_letter(
        gift, requester=operator, site_url=SITE_URL
    )
    gift.refresh_from_db()
    with gift.pdf.open("rb") as handle:
        archive = handle.read()
    with pymupdf.open(stream=archive, filetype="pdf") as doc:
        receipt_text = "\n".join(page.get_text() for page in doc)
    assert "wire-042" in receipt_text
    assert "425.50" in receipt_text
    # Use the worker trace to exercise automatic STARTED handling and replay.
    row = TaskResult.objects.get(task_id=task_id)
    current_app.autodiscover_tasks(force=True)
    trace = build_tracer(
        row.task_name, current_app.tasks[row.task_name], app=current_app, eager=False
    )
    args, kwargs = json.loads(row.task_args), json.loads(row.task_kwargs)
    request = {"id": task_id, "task": row.task_name}
    trace(task_id, args, kwargs, request)
    trace(task_id, args, kwargs, request)
    row.refresh_from_db()
    assert row.status == TaskResultStatus.SUCCESS
    assert json.loads(row.result)["outcome"] == "backend-accepted"
    with pytest.raises(ValueError, match="already issued"):
        letter_operations.issue_letter(gift, requester=operator, site_url=SITE_URL)
    deliver(
        letter_operations.resend_letter(gift, requester=operator, site_url=SITE_URL)
    )
    assert [message.to for message in mailoutbox] == [[gift.donor_email]] * 2
    assert all(message.subject == gift.template.email_subject for message in mailoutbox)
    assert all(message.attachments[0].content == archive for message in mailoutbox)
    gift.refresh_from_db()
    assert gift.last_sent_at


@pytest.mark.django_db
def test_draft_and_template_previews_only_reach_requester(
    gift: DonationThankYouLetters,
    mailoutbox: Any,
) -> None:
    operator = UserFactory.create(is_superuser=True)
    # Admin form input can omit the trailing zeros that the database restores.
    gift.amount = Decimal("425")
    gift.save(update_fields=["amount"])
    for obj in (gift.template, gift):
        deliver(
            letter_operations.schedule_letter_preview(
                obj, requester=operator, site_url=SITE_URL
            )
        )
    assert [message.to for message in mailoutbox] == [[operator.email]] * 2
    assert [message.subject for message in mailoutbox] == [
        gift.template.email_subject,
        gift.template.email_subject,
    ]
    with pymupdf.open(
        stream=mailoutbox[-1].attachments[0].content, filetype="pdf"
    ) as pdf:
        content = "\n".join(page.get_text() for page in pdf)
    assert "preview" not in content.lower()
    assert "wire-042" in content
    assert "$425.00" in content
    gift.refresh_from_db()
    assert not gift.pdf
    assert gift.issued_at is None
    assert gift.last_sent_at is None


@pytest.mark.django_db
def test_template_preview_receipt_id_matches_its_attachment(
    gift: DonationThankYouLetters, tmp_path: Path, settings: Settings, mailoutbox: Any
) -> None:
    source = tmp_path / gift.template.email_template_name
    source.parent.mkdir(parents=True)
    source.write_text("<p>{{ letter.pk }}</p>", encoding="utf-8")
    settings.TEMPLATES = [
        {**engine, "DIRS": [tmp_path, *engine["DIRS"]]} for engine in settings.TEMPLATES
    ]
    operator = UserFactory.create(is_superuser=True)
    deliver(
        letter_operations.schedule_letter_preview(
            gift.template, requester=operator, site_url=SITE_URL
        )
    )
    (message,) = mailoutbox
    (attachment,) = message.attachments
    assert attachment.filename == f"donation-acknowledgment-{message.body}.pdf"
    with pymupdf.open(stream=attachment.content, filetype="pdf") as doc:
        assert message.body in "\n".join(page.get_text() for page in doc)


@pytest.mark.django_db
def test_regeneration_replaces_the_issued_pdf_and_requires_an_explicit_resend(
    gift: DonationThankYouLetters,
    mailoutbox: Any,
    django_capture_on_commit_callbacks: Any,
) -> None:
    operator = UserFactory.create(is_superuser=True)
    pending = letter_operations.issue_letter(
        gift, requester=operator, site_url=SITE_URL
    )
    gift.refresh_from_db()
    acknowledgment_id = gift.pk
    issued_at = gift.issued_at
    old_key = gift.pdf.name
    assert old_key is not None
    gift.donor_name = "Alex Survey Foundation"
    gift.donor_email = "foundation@example.org"
    gift.amount = Decimal("500.50")
    gift.transaction_reference = "wire-052"
    with django_capture_on_commit_callbacks(execute=True):
        letter_operations.regenerate_letter(gift)
        assert gift.pdf.storage.exists(old_key)
    gift.refresh_from_db()
    assert gift.pk == acknowledgment_id
    assert gift.issued_at == issued_at
    assert not gift.pdf.storage.exists(old_key)
    assert gift.last_task_id is None
    assert gift.last_sent_at is None
    assert TaskResult.objects.count() == 1
    assert json.loads(deliver(pending).result)["outcome"] == "skipped"
    assert not mailoutbox

    with gift.pdf.open("rb") as archive:
        updated = archive.read()
    with pymupdf.open(stream=updated, filetype="pdf") as pdf:
        text = "\n".join(page.get_text() for page in pdf)
    assert str(acknowledgment_id) in text
    assert gift.donor_name in text
    assert gift.transaction_reference in text
    assert "500.50" in text
    assert "425.50" not in text
    deliver(
        letter_operations.resend_letter(gift, requester=operator, site_url=SITE_URL)
    )
    assert [message.to for message in mailoutbox] == [["foundation@example.org"]]
    assert mailoutbox[0].attachments[0].content == updated


@pytest.mark.django_db
def test_delivery_failure_retains_issued_pdf(
    gift: DonationThankYouLetters, mailoutbox: Any
) -> None:
    operator = UserFactory.create(is_superuser=True)
    task_id = letter_operations.issue_letter(
        gift, requester=operator, site_url=SITE_URL
    )
    gift.refresh_from_db()
    original_key = gift.pdf.name
    # A misconfigured email backend fails when the worker opens its transport.
    with (
        override_settings(
            MAILERS={"default": {"BACKEND": "missing.backend.Transport"}}
        ),
        pytest.raises(InvalidMailer),
    ):
        deliver(task_id)
    assert not mailoutbox
    assert TaskResult.objects.get(task_id=task_id).status == TaskResultStatus.FAILURE
    gift.refresh_from_db()
    assert gift.last_sent_at is None
    assert gift.pdf.name == original_key
    with gift.pdf.open("rb") as blob:
        assert blob.read().startswith(b"%PDF")


@pytest.mark.django_db
def test_changed_donation_amount_invalidates_review(
    gift: DonationThankYouLetters,
) -> None:
    operator = UserFactory.create(is_superuser=True)
    digest = letter_operations.letter_review_digest(gift)
    gift.amount = Decimal("525.50")
    gift.save(update_fields=["amount"])
    with pytest.raises(ValueError, match="changed"):
        letter_operations.issue_letter(
            gift, requester=operator, site_url=SITE_URL, expected_digest=digest
        )
    gift.refresh_from_db()
    assert not gift.pdf
    assert gift.issued_at is None
    assert not TaskResult.objects.exists()


@pytest.mark.django_db
def test_unrenderable_replacement_preserves_the_saved_gift_and_pdf(
    gift: DonationThankYouLetters, tmp_path: Path, settings: Settings
) -> None:
    operator = UserFactory.create(is_superuser=True)
    pending = letter_operations.issue_letter(
        gift, requester=operator, site_url=SITE_URL
    )
    gift.refresh_from_db()
    old_key = gift.pdf.name
    with gift.pdf.open("rb") as archive:
        original = archive.read()

    source = tmp_path / "campaigns/acknowledgment_letter.html"
    source.parent.mkdir(parents=True)
    source.write_text("{% invalid_pdf_tag %}", encoding="utf-8")
    settings.TEMPLATES = [
        {**engine, "DIRS": [tmp_path, *engine["DIRS"]]} for engine in settings.TEMPLATES
    ]
    gift.amount = Decimal("505.00")
    with pytest.raises(TemplateSyntaxError, match="invalid_pdf_tag"):
        letter_operations.regenerate_letter(gift)
    gift.refresh_from_db()
    assert gift.amount == Decimal("425.50")
    assert str(gift.last_task_id) == pending
    assert gift.pdf.name == old_key
    with gift.pdf.open("rb") as archive:
        assert archive.read() == original


@pytest.mark.django_db
def test_unrenderable_email_rolls_back_issuance_and_cleans_private_file(
    gift: DonationThankYouLetters, tmp_path: Path, settings: Settings
) -> None:
    source = tmp_path / gift.template.email_template_name
    source.parent.mkdir(parents=True)
    source.write_text("{% invalid_email_tag %}", encoding="utf-8")
    settings.TEMPLATES = [
        {**engine, "DIRS": [tmp_path, *engine["DIRS"]]} for engine in settings.TEMPLATES
    ]
    operator = UserFactory.create(is_superuser=True)
    with pytest.raises(TemplateSyntaxError, match="invalid_email_tag"):
        letter_operations.issue_letter(gift, requester=operator, site_url=SITE_URL)
    gift.refresh_from_db()
    assert gift.issued_at is None
    assert not gift.pdf
    assert not gift.pdf.storage.exists(f"{gift.pk}.pdf")
    assert not TaskResult.objects.exists()
