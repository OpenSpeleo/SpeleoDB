# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from importlib import reload
from typing import TYPE_CHECKING

import pytest
from django.contrib import admin
from django.contrib.admin.exceptions import AlreadyRegistered
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from pytest_django.asserts import assertRedirects
from rest_framework import status

from speleodb.users.models import User

if TYPE_CHECKING:
    from django.test.client import Client
    from django.test.client import RequestFactory
    from pytest_django.fixtures import SettingsWrapper


class TestUserAdmin:
    def test_changelist(self, admin_client: Client) -> None:
        url = reverse("admin:users_user_changelist")
        response = admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK, response.data  # type: ignore[attr-defined]

    def test_search(self, admin_client: Client) -> None:
        url = reverse("admin:users_user_changelist")
        response = admin_client.get(url, data={"q": "test"})
        assert response.status_code == status.HTTP_200_OK, response.data  # type: ignore[attr-defined]

    def test_add(self, admin_client: Client) -> None:
        url = reverse("admin:users_user_add")
        response = admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK, response.data  # type: ignore[attr-defined]

        response = admin_client.post(
            url,
            data={
                "email": "new-admin@example.com",
                "password1": "My_R@ndom-P@ssw0rd",
                "password2": "My_R@ndom-P@ssw0rd",
            },
        )
        assert response.status_code == status.HTTP_302_FOUND, response.data  # type: ignore[attr-defined]
        assert User.objects.filter(email="new-admin@example.com").exists()

    def test_view_user(self, admin_client: Client) -> None:
        user = User.objects.get(email="admin@example.com")
        url = reverse("admin:users_user_change", kwargs={"object_id": user.pk})
        response = admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK, response.data  # type: ignore[attr-defined]

    @pytest.fixture
    def _force_allauth(self, settings: SettingsWrapper) -> None:
        settings.DJANGO_ADMIN_FORCE_ALLAUTH = True
        # Reload the admin module to apply the setting change
        import speleodb.users.admin as users_admin  # noqa: PLC0415

        with contextlib.suppress(AlreadyRegistered):
            reload(users_admin)

    @pytest.mark.django_db
    @pytest.mark.usefixtures("_force_allauth")
    def test_allauth_login(self, rf: RequestFactory, settings: SettingsWrapper) -> None:
        request = rf.get("/fake-url")
        request.user = AnonymousUser()
        response = admin.site.login(request)

        # The `admin` login view should redirect to the `allauth` login view
        target_url = reverse(settings.LOGIN_URL) + "?next=" + request.path
        assertRedirects(response, target_url, fetch_redirect_response=False)
