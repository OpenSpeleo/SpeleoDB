# -*- coding: utf-8 -*-

from __future__ import annotations

from types import GeneratorType
from typing import TYPE_CHECKING
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.conf import settings
from django.urls import reverse
from requests.exceptions import ChunkedEncodingError
from requests.exceptions import RequestException
from requests.exceptions import Timeout
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.common.enums import PermissionLevel
from speleodb.git_engine.gitlab_manager import GitlabCredentials

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Mapping

    from django.http.response import HttpResponseBase


SANITIZED_UPSTREAM_ERROR = b"SpeleoDB Git service is temporarily unavailable."
UPSTREAM_TOKEN = "upstream-secret-token"  # noqa: S105
UPSTREAM_TIMEOUT_SECONDS = 30
REQUEST_ATTEMPTS_WITH_RETRY = 2


class TestGitProxyServer(BaseAPIProjectTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )
        self.credentials = GitlabCredentials(
            instance="gitlab.internal.example",
            token=UPSTREAM_TOKEN,
            group_id="42",
            group_name="speleodb",
        )
        self.credentials_patcher = patch(
            "speleodb.git_proxy.views.GitlabCredentials.get",
            return_value=self.credentials,
        )
        self.credentials_patcher.start()
        self.addCleanup(self.credentials_patcher.stop)

    def _info_url(self) -> str:
        endpoint: str = reverse("git_info", kwargs={"id": self.project.id})
        return f"{endpoint}?service=git-upload-pack"

    def _upload_url(self) -> str:
        return reverse("git_service_read", kwargs={"id": self.project.id})

    def _receive_url(self) -> str:
        return reverse("git_service_write", kwargs={"id": self.project.id})

    @staticmethod
    def _upstream_response(
        *,
        status_code: int = status.HTTP_200_OK,
        content_type: str = "application/x-git-upload-pack-advertisement",
        chunks: tuple[bytes, ...] = (),
        reason: str = "OK",
    ) -> MagicMock:
        response = MagicMock()
        response.status_code = status_code
        response.reason = reason
        response.headers = {
            "Content-Type": content_type,
            "Cache-Control": "no-cache",
            "X-Request-ID": "upstream-request-id",
        }
        response.iter_content.return_value = iter(chunks)
        return response

    @staticmethod
    def _response_body(response: HttpResponseBase) -> bytes:
        if response.streaming:
            return b"".join(response.streaming_content)  # type: ignore[attr-defined]
        return response.content  # type: ignore[attr-defined,no-any-return]

    def _assert_sanitized_bad_gateway(self, response: HttpResponseBase) -> None:
        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert response["Content-Type"].split(";", maxsplit=1)[0] == "text/plain"
        assert response["Cache-Control"] == "no-store"
        assert self._response_body(response) == SANITIZED_UPSTREAM_ERROR

    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_info_refs_stream_is_byte_transparent(
        self, request_mock: MagicMock
    ) -> None:
        chunks: tuple[bytes, ...] = (
            b"001e# service=git-upload-",
            b"pack\n0000Git",
            b"Lab\x00\xff",
        )
        upstream_response: MagicMock = self._upstream_response(
            content_type=("Application/X-Git-Upload-Pack-Advertisement; charset=UTF-8"),
            chunks=chunks,
        )
        request_mock.return_value = upstream_response

        response: HttpResponseBase = self.client.get(
            self._info_url(),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == upstream_response.headers["Content-Type"]
        assert response["Cache-Control"] == "no-cache"
        assert self._response_body(response) == b"".join(chunks)
        upstream_response.iter_content.assert_called_once_with(chunk_size=8192)
        upstream_response.close.assert_called_once_with()

    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_service_result_stream_is_byte_transparent(
        self, request_mock: MagicMock
    ) -> None:
        request_body: bytes = b"0011want GitLab\x00\xff0000"
        chunks: tuple[bytes, ...] = (b"0008NA", b"K\nGit", b"Lab\x00\xfe")
        upstream_response: MagicMock = self._upstream_response(
            content_type="application/x-git-upload-pack-result",
            chunks=chunks,
        )
        request_mock.return_value = upstream_response

        response: HttpResponseBase = self.client.post(
            self._upload_url(),
            data=request_body,
            content_type="application/x-git-upload-pack-request",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert self._response_body(response) == b"".join(chunks)
        assert request_mock.call_args.kwargs["data"] == request_body
        upstream_response.close.assert_called_once_with()

    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_receive_pack_result_uses_receive_media_type(
        self, request_mock: MagicMock
    ) -> None:
        self.project.acquire_mutex(self.user)
        upstream_response: MagicMock = self._upstream_response(
            content_type="application/x-git-receive-pack-result",
            chunks=(b"0008NAK\n",),
        )
        request_mock.return_value = upstream_response

        response: HttpResponseBase = self.client.post(
            self._receive_url(),
            data=b"0000",
            content_type="application/x-git-receive-pack-request",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/x-git-receive-pack-result"
        assert self._response_body(response) == b"0008NAK\n"
        upstream_response.close.assert_called_once_with()

    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_upstream_request_isolated_from_client_credentials_and_proxy_headers(
        self, request_mock: MagicMock
    ) -> None:
        upstream_response: MagicMock = self._upstream_response(chunks=(b"0000",))
        request_mock.return_value = upstream_response

        response: HttpResponseBase = self.client.get(
            self._info_url(),
            headers={
                "authorization": self.auth,
                "user-agent": "git/2.50",
                "accept": "application/x-git-upload-pack-advertisement",
                "content-type": "application/x-git-upload-pack-request",
                "git-protocol": "version=2",
                "cache-control": "no-cache",
                "pragma": "no-cache",
                "cookie": "session=client-secret",
                "x-forwarded-for": "203.0.113.20",
                "x-untrusted": "must-not-be-forwarded",
            },
        )
        self._response_body(response)

        call_kwargs: Mapping[str, Any] = request_mock.call_args.kwargs
        upstream_headers: dict[str, str] = {
            key.lower(): value for key, value in call_kwargs["headers"].items()
        }
        assert upstream_headers == {
            "accept": "application/x-git-upload-pack-advertisement",
            "accept-encoding": "identity",
            "cache-control": "no-cache",
            "content-type": "application/x-git-upload-pack-request",
            "git-protocol": "version=2",
            "pragma": "no-cache",
            "user-agent": "git/2.50",
        }
        assert call_kwargs["url"] == (
            f"{settings.GITLAB_HTTP_PROTOCOL}://"
            "gitlab.internal.example/speleodb/"
            f"{self.project.id}.git/info/refs"
        )
        assert self.credentials.token not in call_kwargs["url"]
        assert call_kwargs["auth"] == ("oauth2", self.credentials.token)
        assert call_kwargs["allow_redirects"] is False
        assert call_kwargs["stream"] is True
        assert call_kwargs["timeout"] == UPSTREAM_TIMEOUT_SECONDS
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["data"] is None
        assert call_kwargs["params"]["service"] == "git-upload-pack"

    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_html_success_response_becomes_sanitized_bad_gateway(
        self, request_mock: MagicMock
    ) -> None:
        upstream_response: MagicMock = self._upstream_response(
            content_type="text/html; charset=utf-8",
            chunks=(b"<!DOCTYPE html><title>GitLab</title>",),
        )
        request_mock.return_value = upstream_response

        response: HttpResponseBase = self.client.get(
            self._info_url(), headers={"authorization": self.auth}
        )

        self._assert_sanitized_bad_gateway(response)
        upstream_response.iter_content.assert_not_called()
        upstream_response.close.assert_called_once_with()

    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_wrong_git_media_type_becomes_sanitized_bad_gateway(
        self, request_mock: MagicMock
    ) -> None:
        upstream_response: MagicMock = self._upstream_response(
            content_type="application/x-git-receive-pack-advertisement",
            chunks=(b"0000",),
        )
        request_mock.return_value = upstream_response

        response: HttpResponseBase = self.client.get(
            self._info_url(), headers={"authorization": self.auth}
        )

        self._assert_sanitized_bad_gateway(response)
        upstream_response.iter_content.assert_not_called()
        upstream_response.close.assert_called_once_with()

    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_redirect_and_upstream_error_become_sanitized_bad_gateway(
        self, request_mock: MagicMock
    ) -> None:
        for status_code, reason in (
            (status.HTTP_302_FOUND, "Found"),
            (status.HTTP_401_UNAUTHORIZED, "Unauthorized"),
            (status.HTTP_503_SERVICE_UNAVAILABLE, "Service Unavailable"),
        ):
            with self.subTest(status_code=status_code):
                upstream_response: MagicMock = self._upstream_response(
                    status_code=status_code,
                    content_type="text/html",
                    chunks=(b"<!DOCTYPE html><title>GitLab</title>",),
                    reason=reason,
                )
                request_mock.reset_mock()
                request_mock.return_value = upstream_response

                response: HttpResponseBase = self.client.get(
                    self._info_url(), headers={"authorization": self.auth}
                )

                self._assert_sanitized_bad_gateway(response)
                upstream_response.iter_content.assert_not_called()
                upstream_response.close.assert_called_once_with()

    @patch("speleodb.git_proxy.views.GitlabManager.create_or_clone_project")
    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_first_404_is_closed_then_repository_is_created_and_retried(
        self,
        request_mock: MagicMock,
        create_or_clone_mock: MagicMock,
    ) -> None:
        first_response: MagicMock = self._upstream_response(
            status_code=status.HTTP_404_NOT_FOUND,
            content_type="text/html",
            reason="Not Found",
        )
        second_response: MagicMock = self._upstream_response(chunks=(b"0000",))
        request_mock.side_effect = [first_response, second_response]

        response: HttpResponseBase = self.client.get(
            self._info_url(), headers={"authorization": self.auth}
        )

        assert self._response_body(response) == b"0000"
        assert request_mock.call_count == REQUEST_ATTEMPTS_WITH_RETRY
        create_or_clone_mock.assert_called_once_with(self.project)
        first_response.close.assert_called_once_with()
        second_response.close.assert_called_once_with()

    @patch("speleodb.git_proxy.views.GitlabManager.create_or_clone_project")
    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_repeated_404_closes_both_responses_and_returns_bad_gateway(
        self,
        request_mock: MagicMock,
        create_or_clone_mock: MagicMock,
    ) -> None:
        first_response: MagicMock = self._upstream_response(
            status_code=status.HTTP_404_NOT_FOUND,
            content_type="text/html",
            reason="Not Found",
        )
        second_response: MagicMock = self._upstream_response(
            status_code=status.HTTP_404_NOT_FOUND,
            content_type="text/html",
            reason="Not Found",
        )
        request_mock.side_effect = [first_response, second_response]

        response: HttpResponseBase = self.client.get(
            self._info_url(), headers={"authorization": self.auth}
        )

        self._assert_sanitized_bad_gateway(response)
        assert request_mock.call_count == REQUEST_ATTEMPTS_WITH_RETRY
        create_or_clone_mock.assert_called_once_with(self.project)
        first_response.close.assert_called_once_with()
        second_response.close.assert_called_once_with()

    @patch("speleodb.git_proxy.views.GitlabManager.create_or_clone_project")
    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_404_recovery_failure_is_sanitized_and_does_not_log_secret(
        self,
        request_mock: MagicMock,
        create_or_clone_mock: MagicMock,
    ) -> None:
        first_response: MagicMock = self._upstream_response(
            status_code=status.HTTP_404_NOT_FOUND,
            content_type="text/html",
            reason="Not Found",
        )
        request_mock.return_value = first_response
        create_or_clone_mock.side_effect = RuntimeError(
            f"clone failed for https://oauth2:{UPSTREAM_TOKEN}@gitlab.example/repo"
        )

        with self.assertLogs("speleodb.git_proxy.views", level="WARNING") as logs:
            response: HttpResponseBase = self.client.get(
                self._info_url(), headers={"authorization": self.auth}
            )

        self._assert_sanitized_bad_gateway(response)
        assert request_mock.call_count == 1
        first_response.close.assert_called_once_with()
        assert UPSTREAM_TOKEN not in "\n".join(logs.output)

    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_connection_timeout_returns_sanitized_bad_gateway(
        self, request_mock: MagicMock
    ) -> None:
        request_mock.side_effect = Timeout("upstream timed out")

        response: HttpResponseBase = self.client.get(
            self._info_url(), headers={"authorization": self.auth}
        )

        self._assert_sanitized_bad_gateway(response)

    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_request_exception_returns_sanitized_bad_gateway(
        self, request_mock: MagicMock
    ) -> None:
        request_mock.side_effect = RequestException("upstream request failed")

        response: HttpResponseBase = self.client.get(
            self._info_url(), headers={"authorization": self.auth}
        )

        self._assert_sanitized_bad_gateway(response)

    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_deferred_stream_failure_closes_upstream_response(
        self, request_mock: MagicMock
    ) -> None:
        def broken_stream() -> Iterator[bytes]:
            yield b"partial GitLab packet"
            raise ChunkedEncodingError("upstream stream ended early")

        upstream_response: MagicMock = self._upstream_response()
        upstream_response.iter_content.return_value = broken_stream()
        request_mock.return_value = upstream_response
        response: HttpResponseBase = self.client.get(
            self._info_url(), headers={"authorization": self.auth}
        )

        with pytest.raises(ChunkedEncodingError):
            self._response_body(response)

        upstream_response.close.assert_called_once_with()

    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_partially_consumed_stream_closes_upstream_on_client_disconnect(
        self, request_mock: MagicMock
    ) -> None:
        upstream_response: MagicMock = self._upstream_response(
            chunks=(b"first packet", b"second packet")
        )
        request_mock.return_value = upstream_response
        response: HttpResponseBase = self.client.get(
            self._info_url(), headers={"authorization": self.auth}
        )
        response_iterator = (
            response._iterator  # type: ignore[attr-defined]  # noqa: SLF001
        )
        assert isinstance(response_iterator, GeneratorType)

        assert next(response_iterator) == b"first packet"
        # Close the test client's stream wrapper so it isolates request_finished
        # database cleanup exactly as it does after full response consumption.
        response_iterator.close()

        upstream_response.close.assert_called_once_with()
        assert response.closed
        self.project.refresh_from_db()


class TestGitProxyAccessBoundary(BaseAPIProjectTestCase):
    def _info_url(self) -> str:
        endpoint: str = reverse("git_info", kwargs={"id": self.project.id})
        return f"{endpoint}?service=git-upload-pack"

    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_unauthenticated_request_never_reaches_upstream(
        self, request_mock: MagicMock
    ) -> None:
        response: HttpResponseBase = self.client.get(self._info_url())

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        request_mock.assert_not_called()

    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_invalid_authentication_never_reaches_upstream(
        self, request_mock: MagicMock
    ) -> None:
        response: HttpResponseBase = self.client.get(
            self._info_url(),
            headers={"authorization": "Token invalid-token"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        request_mock.assert_not_called()

    @patch("speleodb.git_proxy.views.requests.api.request")
    def test_user_without_project_read_permission_never_reaches_upstream(
        self, request_mock: MagicMock
    ) -> None:
        response: HttpResponseBase = self.client.get(
            self._info_url(),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        request_mock.assert_not_called()
