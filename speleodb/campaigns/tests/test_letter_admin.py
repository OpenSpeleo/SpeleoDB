from __future__ import annotations

import json
from contextlib import closing
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any

import pymupdf
import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import resolve
from django.urls import reverse
from django.utils import timezone
from django_celery_results.models import TaskResult

from speleodb.campaigns.letter_rendering import example_letter
from speleodb.campaigns.models import DEFAULT_THANK_YOU_TEMPLATE
from speleodb.campaigns.models import DonationThankYouLetters
from speleodb.campaigns.models import DonationThankYouTemplate
from speleodb.users.models import User

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django.test import RequestFactory
    from pytest_django.fixtures import Settings


@pytest.mark.parametrize(
    "path",
    [
        "/admin/campaigns/donationthankyouletters/add/",
        "/admin/campaigns/donationthankyoutemplate/add/",
    ],
)
def test_staff_cannot_access_donor_forms(rf: RequestFactory, path: str) -> None:
    request = rf.get(path)
    request.user = User(is_staff=True, is_active=True, is_superuser=False)
    match = resolve(path)
    with pytest.raises(PermissionDenied):
        match.func(request, **match.kwargs)


@pytest.fixture
def thank_you_template() -> Iterator[DonationThankYouTemplate]:
    template = DonationThankYouTemplate.objects.create(
        name="Acknowledgment", email_subject="Thank you for your gift"
    )
    yield template
    for archived in DonationThankYouLetters.objects.filter(template=template).exclude(
        pdf=""
    ):
        archived.pdf.delete(save=False)


@pytest.fixture
def donor_form(thank_you_template: DonationThankYouTemplate) -> dict[str, str]:
    return {
        "template": str(thank_you_template.pk),
        "donor_name": "Robin Montoya",
        "donor_email": "robin@example.org",
        "amount": "380.00",
        "gift_date": "2026-02-07",
        "payment_method": "Check",
        "transaction_reference": "CHECK-EXAMPLE",
    }


@pytest.mark.django_db
def test_acknowledgment_lists_link_to_records_without_campaign_send_forms(
    admin_client: Client, thank_you_template: DonationThankYouTemplate
) -> None:
    letter = example_letter(thank_you_template)
    letter.save()
    for model_name, pk in (
        ("donationthankyoutemplate", thank_you_template.pk),
        ("donationthankyouletters", letter.pk),
    ):
        response = admin_client.get(reverse(f"admin:campaigns_{model_name}_changelist"))
        assert response.status_code == HTTPStatus.OK
        html = response.content.decode()
        assert reverse(f"admin:campaigns_{model_name}_change", args=[pk]) in html
        assert 'id="campaign-send-' not in html


@pytest.mark.django_db
def test_admin_template_and_draft_previews_target_operator_only(
    admin_client: Client,
    admin_user: User,
    donor_form: dict[str, str],
) -> None:
    template_data = {
        "name": "Second acknowledgment",
        "email_subject": "Your gift receipt",
        "email_template": DEFAULT_THANK_YOU_TEMPLATE,
    }
    for model_name, field, data in (
        ("donationthankyoutemplate", "email_template", template_data),
        ("donationthankyouletters", "template", donor_form),
    ):
        response = admin_client.post(
            reverse(f"admin:campaigns_{model_name}_add"),
            {
                **data,
                "_save_preview": field,
                "recipient": "diverted@example.org",
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json()["task_results_url"]
        assert (
            admin_client.get(response.json()["change_url"]).status_code == HTTPStatus.OK
        )
    assert [
        json.loads(row)["recipient"]
        for row in TaskResult.objects.values_list("task_kwargs", flat=True)
    ] == [admin_user.email, admin_user.email]
    draft = DonationThankYouLetters.objects.get()
    assert not draft.pdf
    assert draft.issued_at is None


@pytest.mark.django_db
def test_issue_review_rejects_changed_subject(
    admin_client: Client,
    donor_form: dict[str, str],
    thank_you_template: DonationThankYouTemplate,
) -> None:
    response = admin_client.post(
        reverse("admin:campaigns_donationthankyouletters_add"),
        {
            **donor_form,
            "_review_letter": "1",
        },
    )
    letter = DonationThankYouLetters.objects.get()
    issue_url = reverse("admin:letter_issue", args=[letter.pk])
    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == issue_url
    review = admin_client.get(issue_url)
    assert donor_form["donor_email"] in review.content.decode()
    thank_you_template.email_subject = "A revised subject"
    thank_you_template.save(update_fields=["email_subject"])
    stale = admin_client.post(
        issue_url, {"confirmation": review.context["confirmation"]}
    )
    assert "changed" in stale.context["error"]
    letter.refresh_from_db()
    assert not letter.pdf
    assert letter.issued_at is None
    assert not TaskResult.objects.exists()


@pytest.mark.django_db
def test_open_draft_form_cannot_mutate_or_delete_issued_letter(
    admin_client: Client,
    donor_form: dict[str, str],
) -> None:
    admin_client.post(
        reverse("admin:campaigns_donationthankyouletters_add"), donor_form
    )
    letter = DonationThankYouLetters.objects.get()
    change_url = reverse(
        "admin:campaigns_donationthankyouletters_change", args=[letter.pk]
    )
    delete_url = reverse(
        "admin:campaigns_donationthankyouletters_delete", args=[letter.pk]
    )
    assert admin_client.get(change_url).status_code == HTTPStatus.OK
    DonationThankYouLetters.objects.filter(pk=letter.pk).update(
        pdf=f"{letter.pk}.pdf", issued_at=timezone.now()
    )
    assert (
        admin_client.post(
            change_url, {**donor_form, "donor_email": "other@example.org"}
        ).status_code
        == HTTPStatus.FORBIDDEN
    )
    assert (
        admin_client.post(delete_url, {"post": "yes"}).status_code
        == HTTPStatus.FORBIDDEN
    )
    letter.refresh_from_db()
    assert letter.donor_email == donor_form["donor_email"]
    assert (
        admin_client.get(reverse("admin:letter_resend", args=[letter.pk])).status_code
        == HTTPStatus.METHOD_NOT_ALLOWED
    )
    assert not TaskResult.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_confirmed_admin_issue_downloads_the_pdf_emailed_to_the_donor(
    admin_user: User,
    donor_form: dict[str, str],
    settings: Settings,
    mailoutbox: Any,
) -> None:
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_STORE_EAGER_RESULT = True
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)
    add_url = reverse("admin:campaigns_donationthankyouletters_add")
    client.get(add_url)
    headers = {"X-CSRFToken": client.cookies["csrftoken"].value}
    response = client.post(
        add_url, {**donor_form, "_review_letter": "1"}, headers=headers
    )
    review_url = response["Location"]
    review = client.get(review_url)
    confirmation = {"confirmation": review.context["confirmation"]}
    assert client.post(review_url, confirmation).status_code == HTTPStatus.FORBIDDEN
    sent = client.post(review_url, confirmation, headers=headers)
    assert sent.status_code == HTTPStatus.FOUND
    letter = DonationThankYouLetters.objects.get()
    assert letter.last_sent_at
    assert client.get(sent["Location"]).status_code == HTTPStatus.OK
    with closing(client.get(reverse("admin:letter_pdf", args=[letter.pk]))) as archived:
        assert archived["Content-Type"] == "application/pdf"
        downloaded = b"".join(archived)
    client.post(review_url, confirmation, headers=headers)
    assert [message.to for message in mailoutbox] == [[donor_form["donor_email"]]]
    assert downloaded.startswith(b"%PDF")
    assert downloaded == mailoutbox[0].attachments[0].content

    duplicate = client.post(add_url, donor_form, headers=headers)
    assert "transaction_reference" in duplicate.context["adminform"].form.errors
    assert DonationThankYouLetters.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_regenerate_issued_letter_under_same_id_then_explicitly_resend(
    admin_client: Client,
    donor_form: dict[str, str],
    settings: Settings,
    mailoutbox: Any,
) -> None:
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_STORE_EAGER_RESULT = True
    review = admin_client.post(
        reverse("admin:campaigns_donationthankyouletters_add"),
        {**donor_form, "_review_letter": "1"},
        follow=True,
    )
    letter = DonationThankYouLetters.objects.get()
    issue_url = reverse("admin:letter_issue", args=[letter.pk])
    admin_client.post(issue_url, {"confirmation": review.context["confirmation"]})
    letter.refresh_from_db()
    original_date = letter.issued_at
    original_pdf = mailoutbox[0].attachments[0].content
    change_url = reverse(
        "admin:campaigns_donationthankyouletters_change", args=[letter.pk]
    )
    regenerate_url = reverse("admin:letter_regenerate", args=[letter.pk])
    assert regenerate_url in admin_client.get(change_url).content.decode()
    changes = {
        **donor_form,
        "donor_name": "Mira Montoya",
        "donor_email": "mira@example.org",
    }
    invalid = admin_client.post(regenerate_url, {**changes, "amount": "-1"})
    assert "amount" in invalid.context["adminform"].form.errors
    assert (
        f"Resending emails the saved PDF to {donor_form['donor_email']}."
        in invalid.content.decode()
    )
    letter.refresh_from_db()
    assert letter.donor_name == donor_form["donor_name"]

    updated = admin_client.post(regenerate_url, changes)
    assert updated.status_code == HTTPStatus.FOUND
    assert updated["Location"] == change_url
    letter.refresh_from_db()
    assert letter.issued_at == original_date
    assert letter.donor_name == changes["donor_name"]
    with letter.pdf.open("rb") as archive:
        regenerated = archive.read()
    assert regenerated != original_pdf
    with pymupdf.open(stream=regenerated, filetype="pdf") as document:
        assert changes["donor_name"] in "".join(page.get_text() for page in document)

    # An explicit regeneration also restores a missing file when the form's
    # donor and gift values are already up to date.
    letter.pdf.delete(save=False)
    admin_client.post(regenerate_url, changes)
    letter.refresh_from_db()
    with letter.pdf.open("rb") as archive:
        current_pdf = archive.read()
    assert current_pdf.startswith(b"%PDF")
    assert len(mailoutbox) == 1
    assert DonationThankYouLetters.objects.count() == 1

    admin_client.post(reverse("admin:letter_resend", args=[letter.pk]))
    assert [message.to for message in mailoutbox] == [
        [donor_form["donor_email"]],
        [changes["donor_email"]],
    ]
    assert mailoutbox[-1].attachments[0].content == current_pdf
