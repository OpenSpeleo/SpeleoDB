# -*- coding: utf-8 -*-

from __future__ import annotations

import re

import pytest
from django.core.cache import cache
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.templatetags.static import static
from django.test import SimpleTestCase
from django.test import TestCase
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from frontend_public.views import APP_STORE_URL
from frontend_public.views import COMPASS_SIDECAR_RELEASE_INFO_CACHE_KEY
from frontend_public.views import COMPASS_SIDECAR_RELEASES_URL
from frontend_public.views import PLAY_STORE_URL
from frontend_public.views import classify_mobile_platform
from frontend_public.views import get_compass_sidecar_release_info
from speleodb.users.tests.factories import UserFactory


class ViewFunctionalityTest(TestCase):
    @parameterized.expand(
        [
            # General routes
            ("home", None),
            ("download", None),
            ("about", None),
            ("people", None),
            ("roadmap", None),
            ("changelog", None),
            ("terms_and_conditions", None),
            ("privacy_policy", None),
            # Webviews
            ("webview_ariane", None),
            # User Auth Management
            ("account_login", None),
            ("account_signup", None),
            ("account_confirm_email", {"key": "abc123-def456:ghi789"}),
            ("account_reset_password", None),
            (
                "account_reset_password_from_key",
                {"uidb36": "test@speleodb.org", "key": "abc123-def456"},
            ),
        ]
    )
    def test_view_unauthenticated(
        self, name: str, kwargs: dict[str, str] | None
    ) -> None:
        self.execute_test(name=name, kwargs=kwargs)

    def test_view_logout(self) -> None:
        user = UserFactory.create()
        self.client.force_login(user)

        self.execute_test(
            name="account_logout", kwargs=None, expected_status=status.HTTP_302_FOUND
        )

    def execute_test(
        self,
        name: str,
        kwargs: dict[str, str] | None,
        expected_status: int = status.HTTP_200_OK,
    ) -> None:
        url = reverse(name, kwargs=kwargs)

        response = self.client.get(url)

        if expected_status != status.HTTP_302_FOUND:
            assert isinstance(response, HttpResponse), type(response)
        else:
            assert isinstance(response, HttpResponseRedirect), type(response)

        assert response.status_code == expected_status

        assert response["Content-Type"].startswith("text/html"), response[
            "Content-Type"
        ]


class AdaptiveDownloadRedirectViewTests(TestCase):
    @parameterized.expand(
        [
            (
                "android",
                "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
                PLAY_STORE_URL,
            ),
            (
                "iphone",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1",
                APP_STORE_URL,
            ),
            (
                "ipad",
                "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1",
                APP_STORE_URL,
            ),
            (
                "ipados_desktop_mode",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1",
                APP_STORE_URL,
            ),
            (
                "desktop",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                None,
            ),
            ("missing", None, None),
            ("empty", "", None),
        ]
    )
    def test_redirects_to_expected_destination(
        self,
        name: str,
        user_agent: str | None,
        expected_mobile_destination: str | None,
    ) -> None:

        response = self.client.get(
            reverse("download_redirect"), headers={"user-agent": user_agent}
        )

        expected_location = (
            reverse("download")
            if expected_mobile_destination is None
            else expected_mobile_destination
        )

        assert isinstance(response, HttpResponseRedirect), type(response)
        assert response.status_code == status.HTTP_302_FOUND
        assert response["Location"] == expected_location


class MobilePlatformClassificationTests(SimpleTestCase):
    @parameterized.expand(
        [
            (
                "android",
                "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36",
                "android",
            ),
            (
                "iphone",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X)",
                "ios",
            ),
            (
                "ipad",
                "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X)",
                "ios",
            ),
            (
                "ipados_desktop_mode",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Mobile/15E148",
                "ios",
            ),
            (
                "desktop",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "unknown",
            ),
            ("empty", "", "unknown"),
        ]
    )
    def test_classify_mobile_platform(
        self,
        name: str,
        user_agent: str,
        expected_platform: str,
    ) -> None:
        assert classify_mobile_platform(user_agent) == expected_platform

class FaviconRedirectTests(SimpleTestCase):
    @parameterized.expand(
        [
            ("favicon", "favicon", "favicon/favicon.ico"),
            ("apple_touch_icon", "apple_touch_icon", "favicon/apple-touch-icon.png"),
            (
                "apple_touch_icon_precomposed",
                "apple_touch_icon_precomposed",
                "favicon/apple-touch-icon.png",
            ),
        ]
    )
    def test_redirects_to_static_url(
        self,
        name: str,
        url_name: str,
        expected_static_path: str,
    ) -> None:
        response = self.client.get(reverse(url_name))
        assert response.status_code == status.HTTP_301_MOVED_PERMANENTLY
        assert response["Location"] == static(expected_static_path)

    def test_precomposed_and_regular_share_target(self) -> None:
        resp_regular = self.client.get(reverse("apple_touch_icon"))
        resp_precomposed = self.client.get(reverse("apple_touch_icon_precomposed"))
        assert resp_regular["Location"] == resp_precomposed["Location"]

    @parameterized.expand(
        [
            ("favicon",),
            ("apple_touch_icon",),
            ("apple_touch_icon_precomposed",),
        ]
    )
    def test_rejects_post(self, url_name: str) -> None:
        response = self.client.post(reverse(url_name))
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    @parameterized.expand(
        [
            ("favicon",),
            ("apple_touch_icon",),
            ("apple_touch_icon_precomposed",),
        ]
    )
    def test_rejects_put(self, url_name: str) -> None:
        response = self.client.put(reverse(url_name))
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    @parameterized.expand(
        [
            ("favicon",),
            ("apple_touch_icon",),
            ("apple_touch_icon_precomposed",),
        ]
    )
    def test_rejects_delete(self, url_name: str) -> None:
        response = self.client.delete(reverse(url_name))
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class AppAdsTxtTests(SimpleTestCase):
    def test_returns_200(self) -> None:
        response = self.client.get(reverse("app-ads.txt"))
        assert response.status_code == status.HTTP_200_OK

    def test_content_type_is_text_plain(self) -> None:
        response = self.client.get(reverse("app-ads.txt"))
        assert response["Content-Type"] == "text/plain"

    def test_body_content(self) -> None:
        response = self.client.get(reverse("app-ads.txt"))
        assert response.content == b"# This app does not use advertising\n"

    def test_rejects_post(self) -> None:
        response = self.client.post(reverse("app-ads.txt"))
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class RobotsTxtTests(SimpleTestCase):
    def test_returns_200(self) -> None:
        response = self.client.get(reverse("robots.txt"))
        assert response.status_code == status.HTTP_200_OK

    def test_content_type_is_text_plain(self) -> None:
        response = self.client.get(reverse("robots.txt"))
        assert response["Content-Type"] == "text/plain"

    def test_disallows_private(self) -> None:
        response = self.client.get(reverse("robots.txt"))
        assert b"Disallow: /private/" in response.content

    def test_disallows_account(self) -> None:
        response = self.client.get(reverse("robots.txt"))
        assert b"Disallow: /account/" in response.content

    def test_disallows_login(self) -> None:
        response = self.client.get(reverse("robots.txt"))
        assert b"Disallow: /login/" in response.content

    def test_disallows_signup(self) -> None:
        response = self.client.get(reverse("robots.txt"))
        assert b"Disallow: /signup/" in response.content

    def test_rejects_post(self) -> None:
        response = self.client.post(reverse("robots.txt"))
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
