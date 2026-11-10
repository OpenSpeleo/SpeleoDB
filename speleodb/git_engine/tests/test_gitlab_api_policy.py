"""Check real GitLab responses and real unavailable-connection retry boundaries."""

from __future__ import annotations

import logging
import socket
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any
from uuid import uuid4

import gitlab.exceptions
import pytest
from django.conf import settings
from django.test import override_settings
from requests.exceptions import ConnectionError as RequestsConnectionError

from speleodb.common.enums import PermissionLevel
from speleodb.git_engine.client import GitlabClient
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.git_engine.tests.live_gitlab import configured_gitlab_client_fixture  # noqa: F401
from speleodb.git_engine.tests.live_gitlab import configured_gitlab_fixture  # noqa: F401
from speleodb.testing.gitlab_pool import get_pool
from speleodb.utils.gitlab_client import BoundedGitlabClient

if TYPE_CHECKING:
    from collections.abc import Generator

    from gitlab import Gitlab
    from requests import Response

    from speleodb.surveys.models import Project


@pytest.fixture
def unavailable_gitlab_url() -> Generator[str]:
    # Binding without listening reserves the port while the real OS rejects
    # connections (or times out on macOS). The transport stays real.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as unused_port:
        unused_port.bind(("127.0.0.1", 0))
        yield f"http://127.0.0.1:{unused_port.getsockname()[1]}"


@pytest.mark.skip_if_lighttest
def test_real_api_requests_carry_token_and_authenticated_identity(
    live_gitlab: Gitlab,
) -> None:
    responses: list[Response] = []

    def observe(response: Response, **kwargs: Any) -> None:
        responses.append(response)

    live_gitlab.session.hooks["response"].append(observe)
    try:
        identity = live_gitlab.http_get("/user")
        group = live_gitlab.groups.get(str(settings.GITLAB_GROUP_ID))
        assert live_gitlab.user is not None
        assert isinstance(identity, dict)
        assert identity["id"] == live_gitlab.user.id
        assert group.full_path == settings.GITLAB_GROUP_NAME
        assert responses
        # Avoid putting credentials in pytest's assertion introspection output.
        authenticated: bool = all(
            response.request.headers.get("PRIVATE-TOKEN") == settings.GITLAB_TOKEN
            for response in responses
        )
        assert authenticated, (
            "Every real GitLab request must carry the configured token"
        )
    finally:
        live_gitlab.session.hooks["response"].remove(observe)


@pytest.mark.skip_if_lighttest
def test_real_unauthorized_response_is_not_retried() -> None:
    client: GitlabClient = GitlabClient(
        f"{settings.GITLAB_HTTP_PROTOCOL}://{settings.GITLAB_HOST_URL}",
        private_token=f"invalid-{uuid4()}",
        keep_base_url=settings.GITLAB_HTTP_PROTOCOL == "http",
    )
    responses: list[Response] = []

    def observe(response: Response, **kwargs: Any) -> None:
        responses.append(response)

    client.session.hooks["response"].append(observe)
    with client:
        with pytest.raises(gitlab.exceptions.GitlabAuthenticationError) as raised:
            client.auth()
        assert raised.value.response_code == HTTPStatus.UNAUTHORIZED
        assert len(responses) == 1
        assert raised.value.response_body == responses[0].content


@pytest.mark.skip_if_lighttest
def test_real_missing_project_is_not_retried_by_default(
    gitlab_client: GitlabClient,
) -> None:
    responses: list[Response] = []

    def observe(response: Response, **kwargs: Any) -> None:
        responses.append(response)

    gitlab_client.session.hooks["response"].append(observe)
    try:
        with pytest.raises(gitlab.exceptions.GitlabGetError) as raised:
            gitlab_client.projects.get(
                f"{settings.GITLAB_GROUP_NAME}/{uuid4()}",
            )
        assert raised.value.response_code == HTTPStatus.NOT_FOUND
        assert len(responses) == 1

        assert all(
            "retry_not_found" not in str(response.request.url) for response in responses
        )
        assert raised.value.response_body == responses[-1].content
        assert raised.value.error_message == responses[-1].json()["message"]
    finally:
        gitlab_client.session.hooks["response"].remove(observe)


@pytest.mark.skip_if_lighttest
def test_real_missing_branch_recovers_after_branch_creation(
    live_gitlab: Gitlab,
) -> None:
    live_project: Project = get_pool().model()
    get_pool().prepare(live_project)
    baseline: str | None = get_pool().slots[PermissionLevel.ADMIN].baseline_sha
    assert baseline is not None
    branch_name: str = f"integration-{uuid4()}"
    with override_settings(DJANGO_GIT_BRANCH_NAME=branch_name):
        assert GitlabManager.get_last_commit_hash(live_project) is None
        remote = live_gitlab.projects.get(
            f"{settings.GITLAB_GROUP_NAME}/{live_project.id}"
        )
        remote.branches.create({"branch": branch_name, "ref": baseline})
        assert GitlabManager.get_last_commit_hash(live_project) == baseline


@pytest.mark.skip_if_lighttest
def test_failed_real_reauthentication_clears_project_cache(
    live_gitlab: Gitlab,
) -> None:
    live_project: Project = get_pool().model()
    get_pool().prepare(live_project)
    assert GitlabManager.get_commit_history(live_project)
    assert GitlabManager._get_project.cache_info().currsize == 1  # noqa: SLF001

    with override_settings(GITLAB_TOKEN=f"invalid-{uuid4()}"):
        GitlabCredentials.get.cache_clear()
        try:
            with pytest.raises(gitlab.exceptions.GitlabAuthenticationError) as raised:
                GitlabManager._initialize()  # noqa: SLF001
            assert raised.value.response_code == HTTPStatus.UNAUTHORIZED
            assert GitlabManager._gl is None  # noqa: SLF001
            assert GitlabManager._get_project.cache_info().currsize == 0  # noqa: SLF001
        finally:
            GitlabCredentials.get.cache_clear()
            GitlabManager._gl = live_gitlab  # noqa: SLF001


@pytest.mark.parametrize(
    ("verb", "retry_transient_errors", "max_retries"),
    [
        ("GET", False, None),
        ("POST", None, None),
        ("GET", None, 0),
    ],
)
def test_unavailable_connections_are_not_repeated_when_retries_are_disabled(
    *,
    unavailable_gitlab_url: str,
    caplog: pytest.LogCaptureFixture,
    verb: str,
    retry_transient_errors: bool | None,
    max_retries: int | None,
) -> None:
    client = BoundedGitlabClient(
        unavailable_gitlab_url,
        private_token=f"unused-{uuid4()}",
        max_attempts=3,
        timeout=1,
    )
    with (
        client,
        caplog.at_level(logging.WARNING, logger="speleodb.utils.gitlab_client"),
        pytest.raises(RequestsConnectionError),
    ):
        client.http_request(
            verb,
            "/user",
            retry_transient_errors=retry_transient_errors,
            max_retries=max_retries,
        )
    assert not any(
        record.name == "speleodb.utils.gitlab_client" for record in caplog.records
    )


@pytest.mark.parametrize("max_attempts", [0, -1])
def test_invalid_attempt_budgets_are_rejected(max_attempts: int) -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        BoundedGitlabClient(
            "http://localhost", private_token=uuid4().hex, max_attempts=max_attempts
        )


@pytest.mark.parametrize("field", ["timeout", "base_delay", "max_delay"])
@pytest.mark.parametrize("value", [float("inf"), float("nan"), 0.0, -1.0])
def test_invalid_delay_budgets_are_rejected(field: str, value: float) -> None:
    invalid_options: dict[str, Any] = {field: value}
    with pytest.raises(ValueError, match="finite and positive"):
        BoundedGitlabClient(
            "http://localhost", private_token=uuid4().hex, **invalid_options
        )


@pytest.mark.parametrize("timeout", [float("inf"), float("nan"), 0.0, -1.0])
def test_invalid_request_timeout_is_rejected(
    unavailable_gitlab_url: str, timeout: float
) -> None:
    client = BoundedGitlabClient(unavailable_gitlab_url, private_token=uuid4().hex)
    with client, pytest.raises(ValueError, match="timeout"):
        client.http_request("GET", "/user", timeout=timeout)


def test_unbounded_request_retries_are_rejected(unavailable_gitlab_url: str) -> None:
    client = BoundedGitlabClient(unavailable_gitlab_url, private_token=uuid4().hex)
    with client, pytest.raises(ValueError, match="max_retries"):
        client.http_request("GET", "/user", max_retries=-1)


@pytest.mark.parametrize("private_token", ["", " ", "\t\n"])
def test_blank_credentials_cannot_create_an_anonymous_client(
    private_token: str,
) -> None:
    with pytest.raises(ValueError, match="nonempty GitLab private token"):
        BoundedGitlabClient("http://localhost", private_token=private_token)
