# -*- coding: utf-8 -*-

from __future__ import annotations

import re

import pytest
from django.core.cache import cache
from django.http import HttpResponse
from django.http import HttpResponseRedirect
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


class CompassSidecarReleaseFetchTests(SimpleTestCase):
    def _cache_key(self) -> str:
        return f"{COMPASS_SIDECAR_RELEASE_INFO_CACHE_KEY}:{self._testMethodName}"

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    def tearDown(self) -> None:
        cache.clear()
        super().tearDown()

    @pytest.mark.skip_if_offline
    def test_fetches_latest_release_info_from_github(self) -> None:
        cache_key = self._cache_key()
        payload = get_compass_sidecar_release_info(cache_key=cache_key)

        assert payload["windows_url"].startswith(
            "https://github.com/OpenSpeleo/speleodb_compass_sidecar/releases/download/"
        )
        assert payload["windows_url"].endswith(".msi")
        assert re.match(r"^\d+\.\d+\.\d+(?:[-+.\w]*)?$", payload["version"])
        assert payload["pub_date"] is None or isinstance(payload["pub_date"], str)

    @pytest.mark.skip_if_offline
    def test_cached_result_is_used_after_first_github_fetch(self) -> None:
        cache_key = self._cache_key()
        first_payload = get_compass_sidecar_release_info(cache_key=cache_key)
        second_payload = get_compass_sidecar_release_info(
            latest_json_url="http://127.0.0.1:1/latest.json",
            cache_key=cache_key,
            fetch_timeout=0.05,
        )
        assert second_payload == first_payload

    def test_falls_back_when_endpoint_is_unreachable(self) -> None:
        cache_key = self._cache_key()
        payload = get_compass_sidecar_release_info(
            latest_json_url="http://127.0.0.1:1/latest.json",
            cache_key=cache_key,
            fetch_timeout=0.05,
        )

        assert payload["windows_url"] == COMPASS_SIDECAR_RELEASES_URL
        assert payload["version"] == "latest"
        assert payload["pub_date"] is None

    def test_uses_cached_release_info_without_network_call(self) -> None:
        cache_key = self._cache_key()
        cached_payload = {
            "windows_url": "https://example.org/pre-cached-sidecar.msi",
            "version": "9.9.9",
            "pub_date": "2026-01-01T00:00:00.000Z",
        }
        cache.set(cache_key, cached_payload, timeout=3600)

        payload = get_compass_sidecar_release_info(
            latest_json_url="http://127.0.0.1:1/latest.json",
            cache_key=cache_key,
            fetch_timeout=0.05,
        )

        assert payload["windows_url"] == "https://example.org/pre-cached-sidecar.msi"
        assert payload["version"] == "9.9.9"
        assert payload["pub_date"] == "2026-01-01T00:00:00.000Z"
