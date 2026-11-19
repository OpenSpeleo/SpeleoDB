from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django_celery_results.models import TaskResult

from speleodb.campaigns.letter_operations import LETTER_TASK
from speleodb.campaigns.models import DonationThankYouLetters
from speleodb.campaigns.models import DonationThankYouTemplate
from speleodb.common.enums import TaskResultStatus
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client


@pytest.mark.django_db
def test_letter_drafts_accept_only_thank_you_templates_and_positive_gifts() -> None:
    template = DonationThankYouTemplate(
        name="Individual gifts", email_subject="Your donation acknowledgment"
    )
    template.full_clean()
    template.save()
    template.email_template = "../email_templates/appeal.html"
    with pytest.raises(ValidationError) as error:
        template.full_clean()
    assert "email_template" in error.value.message_dict
    letter = DonationThankYouLetters(
        template=template,
        donor_name="Field Survey Club",
        donor_email="club@example.org",
        gift_date=timezone.localdate(),
        amount=Decimal("0.01"),
        payment_method="Check",
        transaction_reference="club-check-5",
    )
    letter.full_clean()
    letter.save()
    with pytest.raises(IntegrityError), transaction.atomic():
        DonationThankYouLetters.objects.filter(pk=letter.pk).update(amount=Decimal("0"))
    duplicate = DonationThankYouLetters.objects.get(pk=letter.pk)
    duplicate.pk = uuid4()
    with pytest.raises(IntegrityError), transaction.atomic():
        duplicate.save(force_insert=True)


@pytest.mark.django_db
def test_staff_cannot_read_donor_mail_through_task_results(client: Client) -> None:
    delivery = TaskResult.objects.create(
        task_id=str(uuid4()),
        task_name=LETTER_TASK,
        status=TaskResultStatus.PENDING,
        task_kwargs='{"recipient":"private-gift@example.org"}',
    )
    client.force_login(UserFactory.create(is_staff=True, is_superuser=False))
    url = reverse("admin:django_celery_results_taskresult_change", args=[delivery.pk])
    assert b"private-gift@example.org" not in client.get(url, follow=True).content
    listing = client.get(reverse("admin:django_celery_results_taskresult_changelist"))
    assert delivery.task_id.encode() not in listing.content
    client.force_login(UserFactory.create(is_superuser=True, is_staff=True))
    assert b"private-gift@example.org" in client.get(url).content
