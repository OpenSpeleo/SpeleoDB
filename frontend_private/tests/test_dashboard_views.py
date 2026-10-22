# -*- coding: utf-8 -*-

from __future__ import annotations

from django.conf import settings
from django.test import SimpleTestCase
from django.test import TestCase
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseUserTestCaseMixin


# ------------------------------------------------------------------ #
#  Dashboard page access
# ------------------------------------------------------------------ #
class TestPrivateLandingPageAccess(BaseUserTestCaseMixin, TestCase):
    @parameterized.expand(["user_dashboard", "map_viewer"])
    def test_unauthenticated_redirects_to_login(self, view_name: str) -> None:
        self.client.logout()
        url = reverse(f"private:{view_name}")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_302_FOUND
        assert "/login/" in response.url  # type: ignore[attr-defined]

    @parameterized.expand(["user_dashboard", "map_viewer"])
    def test_authenticated_returns_200(self, view_name: str) -> None:
        self.client.force_login(self.user)
        url = reverse(f"private:{view_name}")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK


# ------------------------------------------------------------------ #
#  Profile page access
# ------------------------------------------------------------------ #
class TestProfilePageAccess(BaseUserTestCaseMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def test_profile_page_renders_current_user(self) -> None:
        url = reverse("private:user_profile")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        html = response.content.decode()
        assert "update_user_info_form" in html
        assert self.user.email in html
        assert '<select id="country"' in html


# ------------------------------------------------------------------ #
#  URL routing
# ------------------------------------------------------------------ #
class TestDashboardURLRouting(SimpleTestCase):
    def test_login_redirect_goes_to_dashboard(self) -> None:
        redirect_url = settings.LOGIN_REDIRECT_URL
        resolved = reverse(redirect_url) if ":" in redirect_url else redirect_url
        assert resolved == "/private/" or redirect_url == "private:user_dashboard"


# ------------------------------------------------------------------ #
#  Sidebar navigation
# ------------------------------------------------------------------ #
class TestSidebarNavigation(BaseUserTestCaseMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def _get_html(self, view_name: str) -> str:
        url = reverse(f"private:{view_name}")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        return response.content.decode()

    def _assert_api_docs_links_visible(self, html: str) -> None:
        assert f'href="{reverse("api-schema")}"' in html
        assert f'href="{reverse("api-docs")}"' in html

    def _assert_api_docs_links_hidden(self, html: str) -> None:
        assert f'href="{reverse("api-schema")}"' not in html
        assert f'href="{reverse("api-docs")}"' not in html

    def test_api_docs_links_hidden_for_regular_user(self) -> None:
        html = self._get_html("user_dashboard")
        self._assert_api_docs_links_hidden(html)

    def test_api_docs_links_visible_for_flagged_regular_user(self) -> None:
        self.user.has_api_doc_access = True
        self.user.save(update_fields=["has_api_doc_access"])

        html = self._get_html("user_dashboard")

        self._assert_api_docs_links_visible(html)
        assert f'href="{reverse("admin:index")}"' not in html

    def test_api_docs_links_visible_for_staff_user(self) -> None:
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])

        html = self._get_html("user_dashboard")

        self._assert_api_docs_links_visible(html)

    def test_api_docs_links_visible_for_superuser(self) -> None:
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])

        html = self._get_html("user_dashboard")

        self._assert_api_docs_links_visible(html)
