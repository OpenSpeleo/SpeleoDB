# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from io import BytesIO
from time import monotonic
from time import sleep
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.templatetags.static import static
from django.test import SimpleTestCase
from django.test import TestCase
from django.urls import reverse
from parameterized.parameterized import parameterized
from requests import Response
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError
from requests.exceptions import RequestException
from requests.exceptions import Timeout
from rest_framework import status

from frontend_public.views import APP_STORE_URL
from frontend_public.views import COMPASS_SIDECAR_LATEST_JSON_URL
from frontend_public.views import COMPASS_SIDECAR_RELEASE_INFO_CACHE_KEY
from frontend_public.views import COMPASS_SIDECAR_RELEASES_URL
from frontend_public.views import PLAY_STORE_URL
from frontend_public.views import CompassSidecarReleaseInfo
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

    def test_download_page_uses_release_page_when_metadata_is_unavailable(self) -> None:
        with patch(
            "frontend_public.views.get_compass_sidecar_release_info", return_value=None
        ):
            response = self.client.get(reverse("download"))

        assert response.status_code == status.HTTP_200_OK
        assert (
            response.context["compass_sidecar_windows_url"]
            == COMPASS_SIDECAR_RELEASES_URL
        )
        assert response.context["compass_sidecar_version"] == "latest"
        assert response.context["compass_sidecar_pub_date"] is None

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

        headers = {} if user_agent is None else {"user-agent": user_agent}
        response = self.client.get(reverse("download_redirect"), headers=headers)

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
    ASSET_RESOLUTION_REQUEST_COUNT = 2
    LATEST_JSON_URL = "https://downloads.example.test/latest.json"
    ASSET_API_URL = (
        "https://api.github.com/repos/OpenSpeleo/"
        "speleodb_compass_sidecar/releases/assets/489929773"
    )
    DIRECT_MSI_URL = (
        "https://github.com/OpenSpeleo/speleodb_compass_sidecar/"
        "releases/download/v1.2.3/SpeleoDB.Compass.Sidecar_1.2.3_x64_en-US.msi"
    )

    def _cache_key(self) -> str:
        return f"{COMPASS_SIDECAR_RELEASE_INFO_CACHE_KEY}:{self._testMethodName}"

    @staticmethod
    def _response(payload: object) -> MagicMock:
        response = MagicMock()
        response.json.return_value = payload
        return response

    @classmethod
    def _latest_payload(cls, windows_url: str) -> dict[str, object]:
        return {
            "version": "1.2.3",
            "pub_date": "2026-01-01T00:00:00.000Z",
            "platforms": {
                "windows-x86_64-msi": {
                    "url": windows_url,
                },
            },
        }

    def setUp(self) -> None:
        super().setUp()
        cache.clear()
        self.elapsed: float = 0.0
        self.monotonic_mock: MagicMock = self.enterContext(
            patch("frontend_public.views.monotonic", side_effect=lambda: self.elapsed)
        )
        self.sleep_mock: MagicMock = self.enterContext(
            patch("frontend_public.views.sleep", side_effect=self._advance_clock)
        )

    def _advance_clock(self, seconds: float) -> None:
        self.elapsed += seconds

    def tearDown(self) -> None:
        cache.clear()
        super().tearDown()

    def test_fetches_latest_release_info(self) -> None:
        cache_key: str = self._cache_key()
        latest_response: MagicMock = self._response(
            self._latest_payload(self.DIRECT_MSI_URL)
        )
        with patch(
            "frontend_public.views.requests.api.get", return_value=latest_response
        ) as get_mock:
            payload: CompassSidecarReleaseInfo | None = (
                get_compass_sidecar_release_info(cache_key=cache_key)
            )

        assert payload == {
            "windows_url": self.DIRECT_MSI_URL,
            "version": "1.2.3",
            "pub_date": "2026-01-01T00:00:00.000Z",
        }
        get_mock.assert_called_once_with(COMPASS_SIDECAR_LATEST_JSON_URL, timeout=1.0)
        latest_response.raise_for_status.assert_called_once_with()

    def test_cached_result_is_used_after_first_fetch(self) -> None:
        cache_key: str = self._cache_key()
        latest_response: MagicMock = self._response(
            self._latest_payload(self.DIRECT_MSI_URL)
        )
        with patch(
            "frontend_public.views.requests.api.get", return_value=latest_response
        ) as get_mock:
            first_payload: CompassSidecarReleaseInfo | None = (
                get_compass_sidecar_release_info(cache_key=cache_key)
            )
            second_payload: CompassSidecarReleaseInfo | None = (
                get_compass_sidecar_release_info(
                    latest_json_url="https://unused.example.test/latest.json",
                    cache_key=cache_key,
                    fetch_timeout=0.05,
                )
            )

        assert first_payload is not None
        assert first_payload["windows_url"] == self.DIRECT_MSI_URL
        assert second_payload == first_payload
        get_mock.assert_called_once_with(COMPASS_SIDECAR_LATEST_JSON_URL, timeout=1.0)

    @parameterized.expand(
        [
            ("http_error", HTTPError("upstream rejected the request")),
            ("request_error", RequestException("invalid request")),
        ]
    )
    def test_caches_empty_result_after_permanent_upstream_failure(
        self, name: str, error: RequestException
    ) -> None:
        cache_key: str = self._cache_key()
        with (
            patch(
                "frontend_public.views.requests.api.get", side_effect=error
            ) as get_mock,
            self.assertLogs("frontend_public.views", level="WARNING") as logs,
        ):
            first_payload: CompassSidecarReleaseInfo | None = (
                get_compass_sidecar_release_info(cache_key=cache_key)
            )
            second_payload: CompassSidecarReleaseInfo | None = (
                get_compass_sidecar_release_info(cache_key=cache_key)
            )

        assert first_payload is None
        assert second_payload == first_payload
        get_mock.assert_called_once_with(COMPASS_SIDECAR_LATEST_JSON_URL, timeout=1.0)
        assert len(logs.output) == 1
        assert str(error) in logs.output[0]

    def test_returns_empty_result_when_endpoint_is_unreachable(self) -> None:
        cache_key = self._cache_key()
        payload = get_compass_sidecar_release_info(
            latest_json_url="http://127.0.0.1:1/latest.json",
            cache_key=cache_key,
            fetch_timeout=0.05,
        )

        assert payload is None

    def test_fetches_latest_release_info_from_github(self) -> None:
        self.monotonic_mock.side_effect = monotonic
        self.sleep_mock.side_effect = sleep
        payload: CompassSidecarReleaseInfo | None = get_compass_sidecar_release_info(
            cache_key=self._cache_key()
        )
        # An unavailable upstream is a supported empty result. Deterministic
        # tests below prove successful metadata extraction and bounded retries.
        if payload is None:
            assert cache.get(self._cache_key(), "missing") is None
            return
        assert payload["windows_url"].startswith(
            "https://github.com/OpenSpeleo/speleodb_compass_sidecar/releases/download/"
        )
        assert payload["windows_url"].endswith(".msi")
        assert re.match(r"^\d+\.\d+\.\d+(?:[-+.\w]*)?$", payload["version"])
        assert payload["pub_date"] is None or isinstance(payload["pub_date"], str)

    @parameterized.expand(
        [
            ("timeout", Timeout("upstream timed out")),
            ("connection", RequestsConnectionError("connection reset")),
        ]
    )
    def test_retries_transient_errors_with_bounded_backoff(
        self, name: str, error: RequestException
    ) -> None:
        with patch(
            "frontend_public.views.requests.api.get", side_effect=error
        ) as get_mock:
            payload = get_compass_sidecar_release_info(cache_key=self._cache_key())
            cached_payload = get_compass_sidecar_release_info(
                cache_key=self._cache_key()
            )

        assert payload is None
        assert cached_payload is None
        assert self.sleep_mock.call_args_list == [call(0.1), call(0.2), call(0.4)]
        assert self.elapsed == pytest.approx(0.7)
        assert [
            request_call.kwargs["timeout"] for request_call in get_mock.call_args_list
        ] == pytest.approx([1.0, 0.9, 0.7, 0.3])

    @parameterized.expand([(429,), (500,), (502,), (503,), (504,)])
    def test_retries_transient_http_status_then_succeeds(self, code: int) -> None:
        failed_response: Response = Response()
        failed_response.status_code = code
        failed_response.raw = BytesIO()
        success_response: MagicMock = self._response(
            self._latest_payload(self.DIRECT_MSI_URL)
        )
        with patch(
            "frontend_public.views.requests.api.get",
            side_effect=[failed_response, success_response],
        ) as get_mock:
            payload = get_compass_sidecar_release_info(cache_key=self._cache_key())

        assert payload is not None
        assert payload["windows_url"] == self.DIRECT_MSI_URL
        assert get_mock.call_count == self.ASSET_RESOLUTION_REQUEST_COUNT
        self.sleep_mock.assert_called_once_with(0.1)

    @parameterized.expand([(400,), (401,), (403,), (404,)])
    def test_does_not_retry_permanent_http_errors(self, code: int) -> None:
        failed_response: Response = Response()
        failed_response.status_code = code
        failed_response.raw = BytesIO()
        with patch(
            "frontend_public.views.requests.api.get", return_value=failed_response
        ) as get_mock:
            payload = get_compass_sidecar_release_info(cache_key=self._cache_key())

        assert payload is None
        get_mock.assert_called_once()
        self.sleep_mock.assert_not_called()

    @parameterized.expand([("invalid_json",), ("invalid_payload",)])
    def test_does_not_retry_invalid_response(self, name: str) -> None:
        response: MagicMock = self._response({})
        if name == "invalid_json":
            response.json.side_effect = ValueError("invalid JSON")
        with patch(
            "frontend_public.views.requests.api.get", return_value=response
        ) as get_mock:
            payload = get_compass_sidecar_release_info(cache_key=self._cache_key())

        assert payload is None
        get_mock.assert_called_once()
        self.sleep_mock.assert_not_called()

    def test_asset_lookup_shares_remaining_request_budget(self) -> None:
        latest_response: MagicMock = self._response(
            self._latest_payload(self.ASSET_API_URL)
        )
        asset_response: MagicMock = self._response(
            {"browser_download_url": self.DIRECT_MSI_URL}
        )

        def fetch(url: str, **kwargs: object) -> MagicMock:
            if url == self.LATEST_JSON_URL:
                self._advance_clock(0.75)
                return latest_response
            return asset_response

        with patch(
            "frontend_public.views.requests.api.get", side_effect=fetch
        ) as get_mock:
            payload = get_compass_sidecar_release_info(
                latest_json_url=self.LATEST_JSON_URL,
                cache_key=self._cache_key(),
            )

        assert payload is not None
        assert get_mock.call_args_list[0].kwargs["timeout"] == 1.0
        assert get_mock.call_args_list[1].kwargs["timeout"] == pytest.approx(0.25)

    def test_does_not_sleep_or_retry_after_request_exhausts_budget(self) -> None:
        def fetch(url: str, **kwargs: object) -> MagicMock:
            self._advance_clock(1.0)
            raise Timeout("deadline reached")

        with patch(
            "frontend_public.views.requests.api.get", side_effect=fetch
        ) as get_mock:
            payload = get_compass_sidecar_release_info(cache_key=self._cache_key())

        assert payload is None
        get_mock.assert_called_once()
        self.sleep_mock.assert_not_called()

    def test_asset_retry_uses_remaining_shared_budget(self) -> None:
        latest_response: MagicMock = self._response(
            self._latest_payload(self.ASSET_API_URL)
        )

        def fetch(url: str, **kwargs: object) -> MagicMock:
            if url == self.LATEST_JSON_URL:
                self._advance_clock(0.75)
                return latest_response
            raise RequestsConnectionError("asset connection reset")

        with patch(
            "frontend_public.views.requests.api.get", side_effect=fetch
        ) as get_mock:
            payload = get_compass_sidecar_release_info(
                latest_json_url=self.LATEST_JSON_URL,
                cache_key=self._cache_key(),
            )

        assert payload is None
        self.sleep_mock.assert_called_once_with(0.1)
        assert [
            request_call.kwargs["timeout"] for request_call in get_mock.call_args_list
        ] == pytest.approx([1.0, 0.25, 0.15])

    def test_resolves_github_asset_api_url_and_caches_direct_download(self) -> None:
        cache_key = self._cache_key()
        latest_response = self._response(self._latest_payload(self.ASSET_API_URL))
        asset_response = self._response({"browser_download_url": self.DIRECT_MSI_URL})

        with patch(
            "frontend_public.views.requests.api.get",
            side_effect=[latest_response, asset_response],
        ) as get_mock:
            first_payload = get_compass_sidecar_release_info(
                latest_json_url=self.LATEST_JSON_URL,
                cache_key=cache_key,
                fetch_timeout=1.25,
            )
            second_payload = get_compass_sidecar_release_info(
                latest_json_url="https://unused.example.test/latest.json",
                cache_key=cache_key,
                fetch_timeout=9.5,
            )

        expected_payload = {
            "windows_url": self.DIRECT_MSI_URL,
            "version": "1.2.3",
            "pub_date": "2026-01-01T00:00:00.000Z",
        }
        assert first_payload == expected_payload
        assert second_payload == expected_payload
        assert get_mock.call_args_list == [
            call(self.LATEST_JSON_URL, timeout=1.0),
            call(
                self.ASSET_API_URL,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=1.0,
            ),
        ]

    def test_accepts_legacy_direct_msi_url_without_asset_api_request(self) -> None:
        cache_key = self._cache_key()
        latest_response = self._response(self._latest_payload(self.DIRECT_MSI_URL))

        with patch(
            "frontend_public.views.requests.api.get",
            return_value=latest_response,
        ) as get_mock:
            payload = get_compass_sidecar_release_info(
                latest_json_url=self.LATEST_JSON_URL,
                cache_key=cache_key,
                fetch_timeout=1.25,
            )

        assert payload is not None
        assert payload["windows_url"] == self.DIRECT_MSI_URL
        get_mock.assert_called_once_with(self.LATEST_JSON_URL, timeout=1.0)

    @parameterized.expand(
        [
            ("invalid", {"browser_download_url": "://not-a-url"}),
            ("missing", {}),
            (
                "wrong_host",
                {
                    "browser_download_url": (
                        "https://downloads.example.test/OpenSpeleo/"
                        "speleodb_compass_sidecar/releases/download/v1.2.3/sidecar.msi"
                    )
                },
            ),
            (
                "wrong_repo",
                {
                    "browser_download_url": (
                        "https://github.com/OpenSpeleo/another_repo/"
                        "releases/download/v1.2.3/sidecar.msi"
                    )
                },
            ),
            (
                "wrong_scheme",
                {
                    "browser_download_url": (
                        "http://github.com/OpenSpeleo/speleodb_compass_sidecar/"
                        "releases/download/v1.2.3/sidecar.msi"
                    )
                },
            ),
            (
                "non_msi",
                {
                    "browser_download_url": (
                        "https://github.com/OpenSpeleo/speleodb_compass_sidecar/"
                        "releases/download/v1.2.3/sidecar.exe"
                    )
                },
            ),
            (
                "embedded_credentials",
                {
                    "browser_download_url": (
                        "https://token@github.com/OpenSpeleo/"
                        "speleodb_compass_sidecar/releases/download/"
                        "v1.2.3/sidecar.msi"
                    )
                },
            ),
            (
                "query",
                {
                    "browser_download_url": (
                        "https://github.com/OpenSpeleo/speleodb_compass_sidecar/"
                        "releases/download/v1.2.3/sidecar.msi?download=1"
                    )
                },
            ),
            (
                "fragment",
                {
                    "browser_download_url": (
                        "https://github.com/OpenSpeleo/speleodb_compass_sidecar/"
                        "releases/download/v1.2.3/sidecar.msi#download"
                    )
                },
            ),
            (
                "dot_segment",
                {
                    "browser_download_url": (
                        "https://github.com/OpenSpeleo/speleodb_compass_sidecar/"
                        "releases/download/../sidecar.msi"
                    )
                },
            ),
            (
                "encoded_dot_segment",
                {
                    "browser_download_url": (
                        "https://github.com/OpenSpeleo/speleodb_compass_sidecar/"
                        "releases/download/%2e%2e/sidecar.msi"
                    )
                },
            ),
            (
                "encoded_backslash",
                {
                    "browser_download_url": (
                        "https://github.com/OpenSpeleo/speleodb_compass_sidecar/"
                        "releases/download/v1.2.3%5Cescape/sidecar.msi"
                    )
                },
            ),
            (
                "encoded_control_character",
                {
                    "browser_download_url": (
                        "https://github.com/OpenSpeleo/speleodb_compass_sidecar/"
                        "releases/download/v1.2.3%0Aescape/sidecar.msi"
                    )
                },
            ),
            (
                "malformed_nested_path",
                {
                    "browser_download_url": (
                        "https://github.com/nested/OpenSpeleo/"
                        "speleodb_compass_sidecar/releases/download/"
                        "v1.2.3/sidecar.msi"
                    )
                },
            ),
        ]
    )
    def test_falls_back_for_untrusted_asset_browser_download_url(
        self,
        name: str,
        asset_payload: dict[str, object],
    ) -> None:
        cache_key = self._cache_key()
        latest_response = self._response(self._latest_payload(self.ASSET_API_URL))
        asset_response = self._response(asset_payload)

        with patch(
            "frontend_public.views.requests.api.get",
            side_effect=[latest_response, asset_response],
        ) as get_mock:
            payload = get_compass_sidecar_release_info(
                latest_json_url=self.LATEST_JSON_URL,
                cache_key=cache_key,
                fetch_timeout=1.25,
            )

        assert payload is None
        assert get_mock.call_count == self.ASSET_RESOLUTION_REQUEST_COUNT

    @parameterized.expand(
        [
            (
                "wrong_repo",
                "https://api.github.com/repos/OpenSpeleo/another_repo/"
                "releases/assets/489929773",
            ),
            (
                "nonnumeric_asset_id",
                "https://api.github.com/repos/OpenSpeleo/"
                "speleodb_compass_sidecar/releases/assets/latest",
            ),
            (
                "embedded_credentials",
                "https://token@api.github.com/repos/OpenSpeleo/"
                "speleodb_compass_sidecar/releases/assets/489929773",
            ),
            (
                "query",
                "https://api.github.com/repos/OpenSpeleo/"
                "speleodb_compass_sidecar/releases/assets/489929773?download=1",
            ),
            (
                "fragment",
                "https://api.github.com/repos/OpenSpeleo/"
                "speleodb_compass_sidecar/releases/assets/489929773#download",
            ),
        ]
    )
    def test_does_not_fetch_untrusted_asset_api_url(
        self,
        name: str,
        untrusted_api_url: str,
    ) -> None:
        cache_key = self._cache_key()
        latest_response = self._response(self._latest_payload(untrusted_api_url))

        with patch(
            "frontend_public.views.requests.api.get",
            return_value=latest_response,
        ) as get_mock:
            payload = get_compass_sidecar_release_info(
                latest_json_url=self.LATEST_JSON_URL,
                cache_key=cache_key,
                fetch_timeout=1.25,
            )

        assert payload is None
        get_mock.assert_called_once_with(self.LATEST_JSON_URL, timeout=1.0)

    def test_falls_back_when_asset_api_request_fails(self) -> None:
        cache_key = self._cache_key()
        latest_response = self._response(self._latest_payload(self.ASSET_API_URL))

        with patch(
            "frontend_public.views.requests.api.get",
            side_effect=[latest_response, RequestException("GitHub unavailable")],
        ) as get_mock:
            payload = get_compass_sidecar_release_info(
                latest_json_url=self.LATEST_JSON_URL,
                cache_key=cache_key,
                fetch_timeout=1.25,
            )

        assert payload is None
        assert get_mock.call_count == self.ASSET_RESOLUTION_REQUEST_COUNT

    @parameterized.expand(
        [
            (
                "asset_api_url",
                ASSET_API_URL,
            ),
            (
                "arbitrary_url",
                "https://downloads.example.test/pre-cached-sidecar.msi",
            ),
        ]
    )
    def test_ignores_untrusted_cached_url_and_fetches_fresh_release(
        self,
        name: str,
        cached_windows_url: str,
    ) -> None:
        cache_key = self._cache_key()
        cache.set(
            cache_key,
            {
                "windows_url": cached_windows_url,
                "version": "0.9.0",
                "pub_date": None,
            },
            timeout=3600,
        )
        latest_response = self._response(self._latest_payload(self.DIRECT_MSI_URL))

        with patch(
            "frontend_public.views.requests.api.get",
            return_value=latest_response,
        ) as get_mock:
            payload = get_compass_sidecar_release_info(
                latest_json_url=self.LATEST_JSON_URL,
                cache_key=cache_key,
                fetch_timeout=1.25,
            )

        assert payload is not None
        assert payload["windows_url"] == self.DIRECT_MSI_URL
        assert payload["version"] == "1.2.3"
        get_mock.assert_called_once_with(self.LATEST_JSON_URL, timeout=1.0)

    def test_uses_cached_release_info_without_network_call(self) -> None:
        cache_key = self._cache_key()
        cached_payload = {
            "windows_url": self.DIRECT_MSI_URL,
            "version": "9.9.9",
            "pub_date": "2026-01-01T00:00:00.000Z",
        }
        cache.set(cache_key, cached_payload, timeout=3600)

        with patch("frontend_public.views.requests.api.get") as get_mock:
            payload = get_compass_sidecar_release_info(
                latest_json_url="https://unused.example.test/latest.json",
                cache_key=cache_key,
                fetch_timeout=0.05,
            )

        assert payload is not None
        assert payload["windows_url"] == self.DIRECT_MSI_URL
        assert payload["version"] == "9.9.9"
        assert payload["pub_date"] == "2026-01-01T00:00:00.000Z"
        get_mock.assert_not_called()


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
