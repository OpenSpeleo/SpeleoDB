# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.admin.sites import AdminSite
from django.urls import reverse
from rest_framework import status

from frontend_public.admin import BoardMemberAdmin
from frontend_public.models import BoardMember

if TYPE_CHECKING:
    from django.test import Client


def test_person_admin_previews_existing_and_missing_photo() -> None:
    admin = BoardMemberAdmin(BoardMember, AdminSite())
    person = BoardMember(photo="test_photo.jpg")
    url = person.get_photo_url()
    assert url is not None
    assert f'src="{url}"' in admin.photo_preview(person)
    assert f'src="{url}"' in admin.photo_preview_large(person)
    person.photo = None
    assert admin.photo_preview(person) == "-"
    assert admin.photo_preview_large(person) == "No photo uploaded"


@pytest.mark.parametrize(
    ("model_name", "label"),
    [
        ("boardmember", "Board of Directors"),
        ("technicalmember", "Technical Steering Committee"),
        ("explorermember", "Explorer Advisory Board"),
        ("scientificmember", "Scientific Advisory Board"),
    ],
)
def test_person_admin_registration(
    admin_client: Client, model_name: str, label: str
) -> None:
    response = admin_client.get(
        reverse(f"admin:frontend_public_{model_name}_changelist")
    )
    assert response.status_code == status.HTTP_200_OK
    assert label in response.content.decode()
