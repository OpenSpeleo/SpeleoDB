# -*- coding: utf-8 -*-

"""Exercise the proxy against configured GitLab and actual Git packet traffic.

Read-only cases share one real repository to avoid exhausting project-creation
limits. Failure cases use real rejected credentials, absent repositories and a
reserved port with no listener. Arbitrary upstream 5xx responses and truncated
HTTP chunks are not fabricated; those require faults in an actual service.
"""

from __future__ import annotations

import base64
import socket
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from email.utils import format_datetime
from pathlib import Path
from types import GeneratorType
from typing import TYPE_CHECKING
from typing import Any

import gitlab.exceptions
import pytest
import requests
from allauth.account.models import EmailAddress
from django.conf import settings
from django.http import HttpResponse
from django.http import StreamingHttpResponse
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from requests.auth import HTTPBasicAuth
from requests.exceptions import ConnectionError as RequestsConnectionError
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import TokenFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.git_engine.client import GitlabClient
from speleodb.git_engine.core import GitFile
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_proxy.views import UPSTREAM_MAX_RETRY_DELAY_SECONDS
from speleodb.git_proxy.views import GitService
from speleodb.git_proxy.views import UpstreamResponseStream
from speleodb.git_proxy.views import get_upstream_retry_delay
from speleodb.git_proxy.views import request_git_upstream
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from collections.abc import Generator

    from django.http.response import HttpResponseBase
    from gitlab.v4.objects.projects import Project as GitlabProject
    from rest_framework.authtoken.models import Token

    from speleodb.surveys.models import Project
    from speleodb.users.models import User

SANITIZED_UPSTREAM_ERROR: bytes = b"SpeleoDB Git service is temporarily unavailable."
DISCOVERY_FAILURE_MAX_SECONDS: float = 10.0
SINGLE_REQUEST_MAX_SECONDS: float = 3.0
# A real blob containing arbitrary bytes catches text decoding or rewriting in
# both the smart-HTTP response and the pack that a Git client consumes.
GIT_FILE_CONTENT: bytes = b"GitLab\x00\xffSpeleoDB\xfe\n" + bytes(range(256)) * 64


@contextmanager
def configured_git_credentials(**overrides: Any) -> Generator[None]:
    """Reload credentials after actual configuration changes, then restore them."""
    GitlabCredentials.get.cache_clear()
    try:
        with override_settings(**overrides):
            yield
    finally:
        GitlabCredentials.get.cache_clear()


@contextmanager
def unavailable_git_port() -> Generator[str]:
    """Reserve a real local port without listening; connections must be refused."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reserved:
        reserved.bind(("127.0.0.1", 0))
        yield f"127.0.0.1:{reserved.getsockname()[1]}"


def packet_line(payload: bytes) -> bytes:
    return f"{len(payload) + 4:04x}".encode("ascii") + payload


def response_body(response: HttpResponseBase) -> bytes:
    if isinstance(response, StreamingHttpResponse):
        content = response.streaming_content
        assert isinstance(content, Iterator)
        return b"".join(content)
    assert isinstance(response, HttpResponse)
    return response.content


def upstream_stream(response: HttpResponseBase) -> UpstreamResponseStream:
    """Inspect the actual stream resource registered by StreamingHttpResponse."""
    assert isinstance(response, StreamingHttpResponse)
    # Django registers these real resources, but its stubs omit the attribute.
    for close in response._resource_closers:  # type: ignore[attr-defined]  # noqa: SLF001
        resource: Any = getattr(close, "__self__", None)
        if isinstance(resource, UpstreamResponseStream):
            return resource
    raise AssertionError("Proxy did not register its upstream stream for cleanup")


@pytest.mark.skip_if_lighttest
class TestGitProxyServer(TestCase):
    client: APIClient
    user: User
    token: Token
    project: Project
    credentials: GitlabCredentials
    repo: GitRepo
    api: GitlabClient
    remote_project: GitlabProject
    head: str
    project_id: uuid.UUID

    @classmethod
    def setUpClass(cls) -> None:
        directory: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        cls.addClassCleanup(directory.cleanup)
        overrides: override_settings = override_settings(
            DJANGO_GIT_PROJECTS_DIR=Path(directory.name)
        )
        overrides.enable()
        cls.addClassCleanup(overrides.disable)
        super().setUpClass()
        # Database rows are fresh per test, matching the repository's global
        # cleanup fixture. Only the read-only remote and local clone are shared.
        cls.project_id = uuid.uuid4()
        remote_project_model: Project = ProjectFactory.build(
            id=cls.project_id, created_by="proxy@example.test"
        )
        cls.credentials = GitlabCredentials.get()
        cls.api = GitlabClient(
            f"{settings.GITLAB_HTTP_PROTOCOL}://{cls.credentials.instance}",
            private_token=cls.credentials.token,
            keep_base_url=settings.GITLAB_HTTP_PROTOCOL == "http",
        )
        cls.addClassCleanup(cls.api.session.close)
        cls.repo = remote_project_model.git_repo
        cls.addClassCleanup(cls.repo.close)
        cls.remote_project = cls.api.projects.get(
            f"{cls.credentials.group_name}/{cls.project_id}"
        )
        cls.addClassCleanup(cls.remote_project.delete)
        file_path: Path = cls.repo.path / "binary.bin"
        file_path.write_bytes(GIT_FILE_CONTENT)
        head: str | None = cls.repo.commit_and_push_project(
            message="Proxy integration binary blob",
            author_name="Proxy Integration",
            author_email="proxy@example.test",
        )
        assert head is not None
        cls.head = head
        assert (
            cls.remote_project.branches.get(settings.DJANGO_GIT_BRANCH_NAME).commit[
                "id"
            ]
            == cls.head
        )

    def setUp(self) -> None:
        super().setUp()
        self.client = APIClient()
        self.user = UserFactory.create()
        self.token = TokenFactory.create(user=self.user)
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )
        self.project = ProjectFactory.create(
            id=self.project_id, created_by=self.user.email
        )
        UserProjectPermissionFactory.create(
            target=self.user, project=self.project, level=PermissionLevel.READ_AND_WRITE
        )

    @property
    def auth(self) -> str:
        return f"Token {self.token.key}"

    def _info_url(self, project: Project | None = None) -> str:
        endpoint: str = reverse("git_info", kwargs={"id": (project or self.project).id})
        return f"{endpoint}?service=git-upload-pack"

    def _service_url(self, service: GitService, project: Project | None = None) -> str:
        return reverse(
            "git_service_read" if service == GitService.UPLOAD else "git_service_write",
            kwargs={"id": (project or self.project).id},
        )

    def _upstream_url(self, path: str, project: Project | None = None) -> str:
        return (
            f"{settings.GITLAB_HTTP_PROTOCOL}://{self.credentials.instance}/"
            f"{self.credentials.group_name}/{(project or self.project).id}.git/{path}"
        )

    def _direct_request(
        self,
        method: str,
        path: str,
        *,
        project: Project | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> requests.Response:
        response: requests.Response = requests.request(
            method,
            self._upstream_url(path, project),
            auth=("oauth2", self.credentials.token),
            headers={"Accept-Encoding": "identity", **(headers or {})},
            params=params,
            data=data,
            timeout=settings.DJANGO_GITLAB_HTTP_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        self.addCleanup(response.close)
        return response

    def _assert_sanitized_bad_gateway(self, response: HttpResponseBase) -> None:
        body: bytes = response_body(response)
        diagnostic: str = body.decode(errors="replace")
        for secret in (self.credentials.token, self.token.key):
            diagnostic = diagnostic.replace(secret, "<redacted>")
        assert response.status_code == status.HTTP_502_BAD_GATEWAY, diagnostic
        assert response["Content-Type"].split(";", maxsplit=1)[0] == "text/plain"
        assert response["Cache-Control"] == "no-store"
        assert body == SANITIZED_UPSTREAM_ERROR

    def _assert_no_credentials(self, diagnostic: str) -> None:
        sensitive_data_detected: bool = any(
            secret in diagnostic for secret in (self.credentials.token, self.token.key)
        )
        assert not sensitive_data_detected, "Credentials leaked into proxy diagnostics"

    def test_info_refs_stream_is_byte_transparent(self) -> None:
        direct: requests.Response = self._direct_request(
            "GET", "info/refs", params={"service": GitService.UPLOAD.value}
        )
        assert direct.status_code == status.HTTP_200_OK
        response: HttpResponseBase = self.client.get(
            self._info_url(), headers={"authorization": self.auth}
        )
        stream: UpstreamResponseStream = upstream_stream(response)

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == direct.headers["Content-Type"]
        assert response_body(response) == direct.content
        assert self.head.encode() in direct.content
        assert direct.content.startswith(packet_line(b"# service=git-upload-pack\n"))
        assert stream.is_closed
        assert stream.response.raw.closed
        self._assert_no_credentials(str(dict(response.items())))

    def test_service_result_stream_contains_a_real_unchanged_git_pack(self) -> None:
        request_body: bytes = (
            packet_line(f"want {self.head}\n".encode())
            + b"0000"
            + packet_line(b"done\n")
        )
        direct: requests.Response = self._direct_request(
            "POST",
            GitService.UPLOAD.value,
            data=request_body,
            headers={"Content-Type": "application/x-git-upload-pack-request"},
        )
        assert direct.status_code == status.HTTP_200_OK
        response: HttpResponseBase = self.client.post(
            self._service_url(GitService.UPLOAD),
            data=request_body,
            content_type="application/x-git-upload-pack-request",
            headers={"authorization": self.auth},
        )
        stream: UpstreamResponseStream = upstream_stream(response)
        assert stream.response.request.body == request_body
        body: bytes = response_body(response)
        assert body == direct.content
        assert body.startswith(b"0008NAK\nPACK")
        assert response["Content-Type"] == "application/x-git-upload-pack-result"
        directory: str = self.enterContext(tempfile.TemporaryDirectory())
        unpacked: GitRepo = GitRepo.init(Path(directory) / "unpacked")
        self.addCleanup(unpacked.close)
        # Indexing the actual returned pack checks its checksum, objects and blob
        # content. A response carrying rewritten bytes cannot satisfy this check.
        with tempfile.TemporaryFile(dir=directory) as pack:
            pack.write(body[len(b"0008NAK\n") :])
            pack.seek(0)
            unpacked.git.index_pack("--stdin", istream=pack)
        blob = unpacked.commit(self.head).tree["binary.bin"]
        assert isinstance(blob, GitFile)
        assert blob.content.getvalue() == GIT_FILE_CONTENT
        assert stream.is_closed
        assert stream.response.raw.closed

    def test_receive_pack_result_uses_receive_media_type(self) -> None:
        self.project.acquire_mutex(self.user)
        direct: requests.Response = self._direct_request(
            "POST",
            GitService.RECEIVE.value,
            data=b"0000",
            headers={"Content-Type": "application/x-git-receive-pack-request"},
        )
        assert direct.status_code == status.HTTP_200_OK
        response: HttpResponseBase = self.client.post(
            self._service_url(GitService.RECEIVE),
            data=b"0000",
            content_type="application/x-git-receive-pack-request",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/x-git-receive-pack-result"
        assert response_body(response) == direct.content
        assert (
            self.remote_project.branches.get(settings.DJANGO_GIT_BRANCH_NAME).commit[
                "id"
            ]
            == self.head
        )

    def test_upstream_request_isolated_from_client_credentials_and_proxy_headers(
        self,
    ) -> None:
        response: HttpResponseBase = self.client.get(
            self._info_url(),
            headers={
                "authorization": self.auth,
                "user-agent": "git/2.50",
                "accept": "application/x-git-upload-pack-advertisement",
                "git-protocol": "version=2",
                "cache-control": "no-cache",
                "pragma": "no-cache",
                "cookie": "session=client-only-cookie",
                "x-forwarded-for": "203.0.113.20",
                "x-untrusted": "must-not-be-forwarded",
            },
        )
        upstream: requests.PreparedRequest = upstream_stream(response).response.request
        expected_auth: requests.PreparedRequest = requests.Request(
            method="GET",
            url=self._upstream_url("info/refs"),
            auth=HTTPBasicAuth("oauth2", self.credentials.token),
        ).prepare()
        # Boolean assertions avoid printing either credential if a regression fails.
        correct_auth: bool = (
            upstream.headers.get("Authorization")
            == (expected_auth.headers["Authorization"])
        )
        assert correct_auth, "Upstream must authenticate using the service credential"
        self._assert_no_credentials(upstream.url or "")
        assert upstream.headers["Git-Protocol"] == "version=2"
        assert upstream.headers["Accept-Encoding"] == "identity"
        assert upstream.headers["User-Agent"] == "git/2.50"
        assert upstream.headers["Cache-Control"] == "no-cache"
        assert upstream.headers["Pragma"] == "no-cache"
        assert all(
            header not in upstream.headers
            for header in ("Cookie", "X-Forwarded-For", "X-Untrusted")
        )
        assert upstream.body is None
        assert response.status_code == status.HTTP_200_OK
        assert packet_line(b"version 2\n") in response_body(response)

    def test_basic_git_token_authentication_reaches_the_real_remote(self) -> None:
        basic_token: str = base64.b64encode(f"oauth2:{self.token.key}".encode()).decode(
            "ascii"
        )
        response: HttpResponseBase = self.client.get(
            self._info_url(), headers={"authorization": f"Basic {basic_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert self.head.encode() in response_body(response)

    def test_invalid_upstream_token_returns_sanitized_bad_gateway(self) -> None:
        invalid_token: str = uuid.uuid4().hex
        with (
            configured_git_credentials(GITLAB_TOKEN=invalid_token),
            self.assertLogs("speleodb.git_proxy.views", level="ERROR") as logs,
        ):
            response: HttpResponseBase = self.client.get(
                self._info_url(), headers={"authorization": self.auth}
            )
        self._assert_sanitized_bad_gateway(response)
        diagnostic: str = "\n".join(logs.output)
        assert "status=401" in diagnostic
        self._assert_no_credentials(diagnostic)
        leaked_invalid_token: bool = invalid_token in diagnostic
        assert not leaked_invalid_token

    def test_first_404_creates_real_repository_and_retries(self) -> None:
        project: Project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user, project=project, level=PermissionLevel.READ_AND_WRITE
        )
        missing: requests.Response = self._direct_request(
            "GET",
            "info/refs",
            project=project,
            params={"service": GitService.UPLOAD.value},
        )
        assert missing.status_code == status.HTTP_404_NOT_FOUND
        assert not project.git_repo_dir.exists()
        response: HttpResponseBase = self.client.get(
            self._info_url(project), headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_200_OK
        body: bytes = response_body(response)
        remote: GitlabProject = self.api.projects.get(
            f"{self.credentials.group_name}/{project.id}"
        )
        self.addCleanup(remote.delete)
        local: GitRepo = GitRepo(project.git_repo_dir)
        self.addCleanup(local.close)
        assert local.head.commit.hexsha.encode() in body
        assert remote.branches.get(settings.DJANGO_GIT_BRANCH_NAME).commit["id"] == (
            local.head.commit.hexsha
        )

    def test_missing_repository_post_is_not_recovered(self) -> None:
        project: Project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user, project=project, level=PermissionLevel.READ_AND_WRITE
        )
        request_body: bytes = (
            packet_line(f"want {self.head}\n".encode())
            + b"0000"
            + packet_line(b"done\n")
        )
        # A flush-only POST is a successful GitLab no-op even for an absent
        # repository. Ask for a real object so the service must resolve it.
        direct: requests.Response = self._direct_request(
            "POST",
            GitService.UPLOAD.value,
            project=project,
            data=request_body,
            headers={"Content-Type": "application/x-git-upload-pack-request"},
        )
        assert direct.status_code == status.HTTP_404_NOT_FOUND
        response: HttpResponseBase = self.client.post(
            self._service_url(GitService.UPLOAD, project),
            data=request_body,
            content_type="application/x-git-upload-pack-request",
            headers={"authorization": self.auth},
        )
        self._assert_sanitized_bad_gateway(response)
        assert not project.git_repo_dir.exists()
        with pytest.raises(gitlab.exceptions.GitlabGetError) as error:
            self.api.projects.get(f"{self.credentials.group_name}/{project.id}")
        assert error.value.response_code == status.HTTP_404_NOT_FOUND

    def test_real_connection_failure_is_sanitized(self) -> None:
        with (
            unavailable_git_port() as host,
            configured_git_credentials(
                GITLAB_HOST_URL=host,
                GITLAB_HTTP_PROTOCOL="http",
                DJANGO_GIT_RETRY_ATTEMPTS=2,
            ),
            self.assertLogs("speleodb.git_proxy.views", level="WARNING") as logs,
        ):
            started: float = time.monotonic()
            response: HttpResponseBase = self.client.get(
                self._info_url(), headers={"authorization": self.auth}
            )
            elapsed: float = time.monotonic() - started
        self._assert_sanitized_bad_gateway(response)
        assert elapsed >= 1.0
        assert elapsed < DISCOVERY_FAILURE_MAX_SECONDS
        self._assert_no_credentials("\n".join(logs.output))

    def test_partially_consumed_stream_closes_upstream_on_client_disconnect(
        self,
    ) -> None:
        response: HttpResponseBase = self.client.get(
            self._info_url(), headers={"authorization": self.auth}
        )
        stream: UpstreamResponseStream = upstream_stream(response)
        assert isinstance(response, StreamingHttpResponse)
        # The test client's real close-wrapper is absent from Django's stubs.
        response_iterator = response._iterator  # type: ignore[attr-defined]  # noqa: SLF001
        assert isinstance(response_iterator, GeneratorType)
        assert next(response_iterator)
        response_iterator.close()
        assert response.closed
        assert stream.is_closed
        assert stream.response.raw.closed
        self.project.refresh_from_db()

    def test_receive_pack_requires_a_real_project_mutex(self) -> None:
        response: HttpResponseBase = self.client.post(
            self._service_url(GitService.RECEIVE),
            data=b"0000",
            content_type="application/x-git-receive-pack-request",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK
        assert b"You did not lock the project" in response_body(response)
        assert (
            self.remote_project.branches.get(settings.DJANGO_GIT_BRANCH_NAME).commit[
                "id"
            ]
            == self.head
        )

    def test_receive_pack_rejects_a_nondefault_branch(self) -> None:
        self.project.acquire_mutex(self.user)
        request_body: bytes = (
            packet_line(
                (
                    f"{self.head} {self.head} "
                    "refs/heads/rejected-branch\x00report-status\n"
                ).encode()
            )
            + b"0000"
        )
        response: HttpResponseBase = self.client.post(
            self._service_url(GitService.RECEIVE),
            data=request_body,
            content_type="application/x-git-receive-pack-request",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK
        assert b"Only commits on branch" in response_body(response)
        with pytest.raises(gitlab.exceptions.GitlabGetError) as error:
            self.remote_project.branches.get("rejected-branch")
        assert error.value.response_code == status.HTTP_404_NOT_FOUND

    def test_invalid_service_returns_git_error_without_upstream_request(self) -> None:
        url: str = reverse("git_info", kwargs={"id": self.project.id})
        response: HttpResponseBase = self.client.get(
            f"{url}?service=invalid", headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_200_OK
        assert b"Invalid service" in response_body(response)


@pytest.mark.parametrize(
    ("retry_after", "expected"),
    [
        (None, 4.0),
        ("", 4.0),
        ("invalid", 4.0),
        ("NaN", 4.0),
        ("inf", 4.0),
        ("1e309", 4.0),
        ("-1", 4.0),
        ("0", 0.0),
        ("3", 3.0),
        ("30", 30.0),
        ("31", None),
    ],
)
def test_upstream_retry_after_value_policy(
    retry_after: str | None, expected: float | None
) -> None:
    assert get_upstream_retry_delay(retry_after, attempt=2) == expected


@pytest.mark.parametrize("seconds", [-5, 0, 3, 29, 35])
def test_upstream_retry_after_date_policy(seconds: int) -> None:
    requested_time = timezone.now() + timedelta(seconds=seconds)
    retry_after: str = format_datetime(requested_time, usegmt=True)
    delay: float | None = get_upstream_retry_delay(retry_after, attempt=0)
    if seconds > UPSTREAM_MAX_RETRY_DELAY_SECONDS:
        assert delay is None
    elif seconds <= 0:
        assert delay == 0.0
    else:
        assert delay is not None
        # HTTP dates have one-second precision; allow clock advancement while
        # exercising the application's real clock rather than replacing it.
        assert max(0, seconds - 2) <= delay <= seconds


@pytest.mark.parametrize("attempt", [0, 1, 2, 3, 4, 5, 8, 1000])
def test_default_retry_backoff_is_capped(attempt: int) -> None:
    assert get_upstream_retry_delay(None, attempt=attempt) == min(
        2 ** min(attempt, 5), UPSTREAM_MAX_RETRY_DELAY_SECONDS
    )


@pytest.mark.parametrize(
    ("discovery", "method"),
    [(False, "GET"), (True, "POST"), (False, "POST"), (True, "HEAD")],
)
def test_only_discovery_get_waits_to_retry(discovery: bool, method: str) -> None:
    with unavailable_git_port() as host:
        started: float = time.monotonic()
        with pytest.raises(RequestsConnectionError):
            request_git_upstream(
                discovery=discovery,
                method=method,
                url=f"http://{host}/info/refs",
                timeout=1,
            )
        # The default discovery budget waits at least 15 seconds. A generous
        # real-clock bound detects accidentally applying it to POST/HEAD.
        assert time.monotonic() - started < SINGLE_REQUEST_MAX_SECONDS


@pytest.mark.parametrize("attempts", [-1, 0, True, 1.5])
def test_upstream_rejects_invalid_attempt_budget(attempts: float) -> None:
    with (
        override_settings(DJANGO_GIT_RETRY_ATTEMPTS=attempts),
        pytest.raises(ValueError, match="positive integer"),
    ):
        request_git_upstream(discovery=True, method="GET")


class TestGitProxyAccessBoundary(BaseAPIProjectTestCase):
    def _info_url(self) -> str:
        endpoint: str = reverse("git_info", kwargs={"id": self.project.id})
        return f"{endpoint}?service=git-upload-pack"

    def test_unauthenticated_request_is_rejected_before_unavailable_upstream(
        self,
    ) -> None:
        with (
            unavailable_git_port() as host,
            configured_git_credentials(
                GITLAB_HOST_URL=host, GITLAB_HTTP_PROTOCOL="http"
            ),
        ):
            response: HttpResponseBase = self.client.get(self._info_url())
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert not self.project.git_repo_dir.exists()

    def test_invalid_authentication_is_rejected_before_unavailable_upstream(
        self,
    ) -> None:
        with (
            unavailable_git_port() as host,
            configured_git_credentials(
                GITLAB_HOST_URL=host, GITLAB_HTTP_PROTOCOL="http"
            ),
        ):
            response: HttpResponseBase = self.client.get(
                self._info_url(), headers={"authorization": "Token invalid-token"}
            )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert not self.project.git_repo_dir.exists()

    def test_user_without_read_permission_is_rejected_before_unavailable_upstream(
        self,
    ) -> None:
        with (
            unavailable_git_port() as host,
            configured_git_credentials(
                GITLAB_HOST_URL=host, GITLAB_HTTP_PROTOCOL="http"
            ),
        ):
            response: HttpResponseBase = self.client.get(
                self._info_url(), headers={"authorization": self.auth}
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not self.project.git_repo_dir.exists()
