"""Explicit administrator issuance, preview and delivery of donor acknowledgments."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import validate_email
from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone
from django_celery_results.models import TaskResult

from speleodb.background_jobs.operations import _publish
from speleodb.campaigns.letter_rendering import example_letter
from speleodb.campaigns.letter_rendering import render_letter_email
from speleodb.campaigns.letter_rendering import render_letter_pdf
from speleodb.campaigns.models import DonationThankYouLetters
from speleodb.campaigns.models import DonationThankYouTemplate
from speleodb.common.enums import TaskResultStatus
from speleodb.users.models import LogEntry

if TYPE_CHECKING:
    from django.core.files.storage import Storage

    from speleodb.users.models import User

logger = logging.getLogger(__name__)
LETTER_TASK = "speleodb.campaigns.tasks.send_donation_letter"
LETTER_TIME_LIMIT = 120


def letter_review_digest(
    obj: DonationThankYouLetters | DonationThankYouTemplate,
) -> str:
    """Bind a confirmation to the donor, gift and selected email template."""
    data = model_to_dict(obj)
    data["id"] = obj.pk
    if isinstance(obj, DonationThankYouLetters):
        data["amount"] = f"{obj.amount:.2f}"
        data["template"] = model_to_dict(obj.template)
    return hashlib.sha256(
        json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True).encode()
    ).hexdigest()


def _require_operator(requester: User) -> None:
    if not (requester.is_active and requester.is_superuser):
        raise PermissionDenied


def _queue_letter(
    obj: DonationThankYouTemplate | DonationThankYouLetters,
    *,
    requester: User,
    site_url: str,
    preview: bool,
) -> str:
    letter = example_letter(obj) if isinstance(obj, DonationThankYouTemplate) else obj
    recipient = requester.email if preview else letter.donor_email
    validate_email(recipient)
    plain, html = render_letter_email(letter, site_url=site_url)
    task_id = str(uuid4())
    kwargs = {
        "recipient": recipient,
        "subject": letter.template.email_subject,
        "plain": plain,
        "html": html,
    }
    if preview:
        kwargs["preview_model"] = (
            "template" if isinstance(obj, DonationThankYouTemplate) else "draft"
        )
        kwargs["review_digest"] = letter_review_digest(obj)
    TaskResult.objects.create(
        task_id=task_id,
        task_name=LETTER_TASK,
        status=TaskResultStatus.PENDING,
        task_args=json.dumps([str(obj.pk)]),
        task_kwargs=json.dumps(kwargs),
        content_type="application/json",
        content_encoding="utf-8",
        meta=json.dumps(
            {
                "operation": "donation-letter",
                "publication": "unattempted",
                "stage": "awaiting publication",
                "time_limit": LETTER_TIME_LIMIT,
                "deadline": (
                    timezone.now() + timedelta(seconds=LETTER_TIME_LIMIT)
                ).isoformat(),
            }
        ),
    )
    LogEntry.record(
        actor_email=requester.email,
        action_flag=LogEntry.Action.ACTION,
        obj=obj,
        change_message="Requested acknowledgment preview."
        if preview
        else "Requested acknowledgment delivery.",
        details={"task_ids": [task_id]},
    )
    if not preview:
        DonationThankYouLetters.objects.filter(pk=letter.pk).update(
            last_task_id=task_id
        )
    return task_id


def schedule_letter_preview(
    obj: DonationThankYouTemplate | DonationThankYouLetters,
    *,
    requester: User,
    site_url: str,
) -> str:
    _require_operator(requester)
    with transaction.atomic():
        task_id = _queue_letter(
            obj, requester=requester, site_url=site_url, preview=True
        )
        transaction.on_commit(partial(_publish, [task_id]))
    return task_id


def _validate_issuance(
    letter: DonationThankYouLetters, expected_digest: str | None
) -> None:
    if letter.issued_at is not None:
        raise ValueError("This acknowledgment was already issued.")
    if expected_digest is not None and letter_review_digest(letter) != expected_digest:
        raise ValueError("The acknowledgment changed. Review it again before issuing.")
    letter.template.full_clean()
    letter.full_clean()


def _delete_pdf(storage: Storage, name: str | None) -> None:
    if name:
        try:
            storage.delete(name)
        except Exception:
            logger.exception("Could not delete unused acknowledgment PDF %s", name)


def issue_letter(
    letter: DonationThankYouLetters,
    *,
    requester: User,
    site_url: str,
    expected_digest: str | None = None,
) -> str:
    _require_operator(requester)
    uploaded: str | None = None
    try:
        # S3 cannot roll back with the database. Own the outer commit so its
        # failure is observable before handing the issued letter to Celery.
        with transaction.atomic(durable=True):
            letter = (
                DonationThankYouLetters.objects.select_for_update()
                .select_related("template")
                .get(pk=letter.pk)
            )
            _validate_issuance(letter, expected_digest)
            letter.issued_at = timezone.now()
            with ContentFile(render_letter_pdf(letter)) as content:
                letter.pdf.save(f"{letter.pk}.pdf", content, save=False)
            uploaded = letter.pdf.name
            letter.save(update_fields=["issued_at", "pdf"])
            task_id = _queue_letter(
                letter, requester=requester, site_url=site_url, preview=False
            )
    except Exception:
        _delete_pdf(letter.pdf.storage, uploaded)
        raise
    transaction.on_commit(partial(_publish, [task_id]))
    return task_id


def _require_issued_pdf(letter: DonationThankYouLetters, *, action: str) -> None:
    if letter.issued_at is None or not letter.pdf:
        raise ValueError(f"Issue the acknowledgment before {action}.")


def resend_letter(
    letter: DonationThankYouLetters, *, requester: User, site_url: str
) -> str:
    _require_operator(requester)
    with transaction.atomic():
        letter = (
            DonationThankYouLetters.objects.select_for_update()
            .select_related("template")
            .get(pk=letter.pk)
        )
        _require_issued_pdf(letter, action="resending")
        task_id = _queue_letter(
            letter, requester=requester, site_url=site_url, preview=False
        )
        transaction.on_commit(partial(_publish, [task_id]))
    return task_id


def regenerate_letter(letter: DonationThankYouLetters) -> None:
    """Save the edited gift and replace the file while preserving its issue date."""
    uploaded: str | None = None
    try:
        # Own the commit so a database failure can discard the uploaded replacement.
        with transaction.atomic(durable=True):
            stored = DonationThankYouLetters.objects.select_for_update().get(
                pk=letter.pk
            )
            _require_issued_pdf(stored, action="regenerating its PDF")
            letter.issued_at = stored.issued_at
            letter.full_clean()
            with ContentFile(render_letter_pdf(letter)) as content:
                letter.pdf.save(f"{uuid4()}.pdf", content, save=False)
            uploaded = letter.pdf.name
            # A pending send belongs to the gift and attachment that were confirmed.
            letter.last_task_id = None
            letter.last_sent_at = None
            letter.save()
            # Keep the old file available until its replacement is committed.
            transaction.on_commit(
                partial(_delete_pdf, stored.pdf.storage, stored.pdf.name)
            )
    except Exception:
        _delete_pdf(letter.pdf.storage, uploaded)
        raise
