from __future__ import annotations

import hashlib
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit
from uuid import UUID

import pytest
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from pytest_django.asserts import assertContains
from tablib.core import Dataset

from frontend_public.models import OrganizationSupporter
from frontend_public.models import PersonSupporter
from speleodb.api.v2.tests.file_utils import sha256_from_url
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client


@pytest.mark.django_db
def test_organization_cannot_be_listed_without_logo_and_website(
    admin_client: Client,
) -> None:
    response = admin_client.post(
        reverse("admin:frontend_public_organizationsupporter_add"),
        {"name": "Survey Club"},
    )
    assert response.status_code == HTTPStatus.OK
    assert set(response.context["adminform"].form.errors) == {"website", "logo"}


@pytest.mark.django_db
def test_person_can_be_listed_without_website_but_only_web_links_are_valid(
    admin_client: Client,
) -> None:
    url = reverse("admin:frontend_public_personsupporter_add")
    name = "Field Surveyor"
    invalid = admin_client.post(url, {"name": name, "website": "ftp://example.org"})
    assert "website" in invalid.context["adminform"].form.errors
    assert not PersonSupporter.objects.exists()
    saved = admin_client.post(url, {"name": name})
    assert saved.status_code == HTTPStatus.FOUND
    assert PersonSupporter.objects.get(name=name).website == ""


@pytest.mark.django_db
def test_staff_can_export_and_reimport_supporting_people(client: Client) -> None:
    client.force_login(UserFactory.create(is_staff=True, is_superuser=False))
    person = PersonSupporter.objects.create(
        name="Rae Lee", website="https://example.org"
    )
    export_url = reverse("admin:frontend_public_personsupporter_export")
    form = client.get(export_url).context["form"]
    selection = {
        name: "on"
        for name, field in form.fields.items()
        if isinstance(field, forms.BooleanField)
    }
    csv_format = next(
        value
        for value, label in form.fields["format"].choices
        if str(label).casefold() == "csv"
    )
    exported = client.post(
        export_url, {**selection, "format": csv_format, "resource": "0"}
    )
    assert exported["Content-Type"].startswith("text/csv")
    data = Dataset().load(exported.content.decode("utf-8-sig"), format="csv")
    assert data.dict == [
        {"id": str(person.pk), "name": "Rae Lee", "website": "https://example.org"}
    ]

    updates = Dataset(headers=data.headers)
    updates.append([data.dict[0]["id"], "Rae Lin", ""])
    updates.append(["", "Rae Lee", "https://example.org/rae"])
    import_url = reverse("admin:frontend_public_personsupporter_import")
    import_form = client.get(import_url).context["form"]
    csv_import = next(
        value
        for value, label in import_form.fields["format"].choices
        if str(label).casefold() == "csv"
    )
    invalid = SimpleUploadedFile(
        "people.csv",
        f"id,name,website\n{person.pk},Rae Lin,ftp://example.org\n,   ,\n".encode(),
        "text/csv",
    )
    rejected = client.post(import_url, {"format": csv_import, "import_file": invalid})
    assert "website" in rejected.context["result"].invalid_rows[0].error.message_dict
    assert "name" in rejected.context["result"].invalid_rows[1].error.message_dict
    person.refresh_from_db()
    assert person.website == "https://example.org"

    upload = SimpleUploadedFile(
        "people.csv", updates.export("csv").encode(), "text/csv"
    )
    preview = client.post(import_url, {"format": csv_import, "import_file": upload})
    assert PersonSupporter.objects.filter(name="Rae Lee").count() == 1
    assert not PersonSupporter.objects.filter(name="Rae Lin").exists()
    confirmed = client.post(
        reverse("admin:frontend_public_personsupporter_process_import"),
        preview.context["confirm_form"].initial,
    )
    assert confirmed.status_code == HTTPStatus.FOUND
    person.refresh_from_db()
    assert (person.name, person.website) == ("Rae Lin", "")
    assert PersonSupporter.objects.exclude(pk=person.pk).get().name == "Rae Lee"


@pytest.mark.django_db
def test_organization_admin_rejects_disguised_unsupported_logo(
    admin_client: Client,
) -> None:
    with BytesIO() as data, Image.new("RGB", (8, 4)) as image:
        image.save(data, format="GIF")
        logo = SimpleUploadedFile("logo.png", data.getvalue(), content_type="image/png")
        response = admin_client.post(
            reverse("admin:frontend_public_organizationsupporter_add"),
            {"name": "Survey Club", "website": "https://example.org", "logo": logo},
        )
    assert "logo" in response.context["adminform"].form.errors
    assert not OrganizationSupporter.objects.exists()


@pytest.mark.django_db
@pytest.mark.skip_if_lighttest
@pytest.mark.parametrize("upload_name", ["wordmark.png", "wordmark.heic"])
def test_uploaded_organization_wordmark_is_served_intact(
    admin_client: Client,
    client: Client,
    upload_name: str,
) -> None:
    with BytesIO() as data, Image.new("RGBA", (48, 12), (0, 0, 0, 0)) as image:
        image.putpixel((24, 6), (255, 255, 255, 255))
        image.save(data, format="PNG")
        content = data.getvalue()
        logo = SimpleUploadedFile(upload_name, content, content_type="image/png")
        response = admin_client.post(
            reverse("admin:frontend_public_organizationsupporter_add"),
            {"name": "Survey Club", "website": "https://example.org", "logo": logo},
        )
    assert response.status_code == HTTPStatus.FOUND
    organization = OrganizationSupporter.objects.get(name="Survey Club")
    try:
        assertContains(client.get(reverse("supporters")), organization.name)
        url = organization.logo.url
        parsed = urlsplit(url)
        filename = Path(parsed.path)
        assert filename.parts[-4:-1] == ("media", "supporters", "organizations")
        assert filename.name == f"{UUID(filename.stem)}.png"
        assert not parsed.query
        # A browser GET must return the original wide image, including its alpha.
        assert sha256_from_url(url) == hashlib.sha256(content).hexdigest()
    finally:
        organization.logo.delete(save=False)


@pytest.mark.django_db
@pytest.mark.skip_if_lighttest
def test_uploaded_heic_logo_is_served_as_jpeg(admin_client: Client) -> None:
    with BytesIO() as data, Image.new("RGB", (48, 12)) as image:
        image.save(data, format="HEIF")
        logo = SimpleUploadedFile("wordmark.HEIC", data.getvalue(), "image/heic")
        response = admin_client.post(
            reverse("admin:frontend_public_organizationsupporter_add"),
            {"name": "Survey Club", "website": "https://example.org", "logo": logo},
        )
    assert response.status_code == HTTPStatus.FOUND
    organization = OrganizationSupporter.objects.get(name="Survey Club")
    try:
        assert urlsplit(organization.logo.url).path.endswith(".jpg")
        with organization.logo.open() as stored, Image.open(stored) as image:
            assert image.format == "JPEG"
            assert image.size == (48, 12)
    finally:
        organization.logo.delete(save=False)


@pytest.mark.skip_if_lighttest
def test_imported_heif_with_jpg_filename_is_converted_to_jpeg() -> None:
    organization = OrganizationSupporter()
    with BytesIO() as data, Image.new("RGB", (48, 12)) as image:
        image.save(data, format="HEIF")
        with SimpleUploadedFile("logo.jpg", data.getvalue(), "image/jpeg") as upload:
            organization.logo.save("logo.jpg", upload, save=False)
    try:
        with organization.logo.open() as stored, Image.open(stored) as decoded:
            assert decoded.format == "JPEG"
    finally:
        organization.logo.delete(save=False)
