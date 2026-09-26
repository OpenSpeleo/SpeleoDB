"""Deterministic retry policy tests; real service coverage lives alongside these."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from dataclasses import field
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any
from uuid import uuid4

import gitlab
import pytest
from gitlab.exceptions import GitlabCreateError
from gitlab.exceptions import GitlabGetError
from gitlab.exceptions import GitlabHttpError
from requests import Response
from requests.exceptions import Timeout

from speleodb.git_engine.gitlab_manager import GitlabManagerCls
from speleodb.surveys.models import Project
from speleodb.utils.gitlab_client import BoundedGitlabClient

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


def missing_project() -> GitlabHttpError:
    return GitlabHttpError("Project Not Found", HTTPStatus.NOT_FOUND, b"missing")


@dataclass
class RequestScript:
    """Supply SDK outcomes without opening a connection or changing live fixtures."""

    outcomes: list[Exception | None] = field(default_factory=list)
    calls: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)
    sleeps: list[float] = field(default_factory=list)

    def request(self, verb: str, path: str, **kwargs: Any) -> Response:
        self.calls.append((verb, path, kwargs))
        assert self.outcomes, "Unexpected request after the scripted retry budget"
        outcome: Exception | None = self.outcomes.pop(0)
        if outcome is not None:
            raise outcome
        response: Response = Response()
        response.status_code = HTTPStatus.OK
        response.headers["Content-Type"] = "application/json"
        response._content = b'{"id": 1}'  # noqa: SLF001
        return response


@pytest.fixture
def request_script(monkeypatch: pytest.MonkeyPatch) -> RequestScript:
    script: RequestScript = RequestScript()

    def request(client: gitlab.Gitlab, verb: str, path: str, **kwargs: Any) -> Response:
        return script.request(verb, path, **kwargs)

    monkeypatch.setattr(gitlab.Gitlab, "http_request", request)
    monkeypatch.setattr("speleodb.utils.gitlab_client.time.sleep", script.sleeps.append)
    return script


@pytest.fixture
def bounded_client(request_script: RequestScript) -> Generator[BoundedGitlabClient]:
    client: BoundedGitlabClient = BoundedGitlabClient(
        "https://gitlab.invalid", private_token=uuid4().hex
    )
    try:
        yield client
    finally:
        client.session.close()


@pytest.mark.parametrize("verb", ["GET", "HEAD"])
@pytest.mark.parametrize("missing_count", [0, 1, 4])
def test_opted_in_lookup_recovers_with_exponential_backoff(
    bounded_client: BoundedGitlabClient,
    request_script: RequestScript,
    verb: str,
    missing_count: int,
) -> None:
    request_script.outcomes = [missing_project() for _ in range(missing_count)] + [None]
    response: Response = bounded_client.http_request(
        verb, "/projects/example", retry_not_found=True
    )
    assert response.status_code == HTTPStatus.OK
    assert len(request_script.calls) == missing_count + 1
    assert request_script.sleeps == [1, 2, 4, 8][:missing_count]
    for _, _, options in request_script.calls:
        assert "retry_not_found" not in options
        assert options["max_retries"] == 0
        assert options["retry_transient_errors"] is False


def test_exhausted_lookup_preserves_final_error_without_extra_sleep(
    bounded_client: BoundedGitlabClient, request_script: RequestScript
) -> None:
    final_error: GitlabHttpError = missing_project()
    request_script.outcomes = [*[missing_project() for _ in range(4)], final_error]
    with pytest.raises(GitlabHttpError) as raised:
        bounded_client.http_request("GET", "/projects/example", retry_not_found=True)
    assert raised.value is final_error
    assert len(request_script.calls) == 5  # noqa: PLR2004
    assert request_script.sleeps == [1, 2, 4, 8]


def test_transient_failures_and_missing_responses_share_one_budget(
    bounded_client: BoundedGitlabClient, request_script: RequestScript
) -> None:
    final_error: Timeout = Timeout("final timeout")
    request_script.outcomes = [
        Timeout("initial timeout"),
        missing_project(),
        GitlabHttpError("unavailable", HTTPStatus.SERVICE_UNAVAILABLE),
        missing_project(),
        final_error,
    ]
    with pytest.raises(Timeout) as raised:
        bounded_client.http_request("GET", "/projects/example", retry_not_found=True)
    assert raised.value is final_error
    assert len(request_script.calls) == 5  # noqa: PLR2004
    assert request_script.sleeps == [1, 2, 4, 8]


@pytest.mark.parametrize("status", [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN])
def test_authorization_errors_are_immediate(
    bounded_client: BoundedGitlabClient,
    request_script: RequestScript,
    status: HTTPStatus,
) -> None:
    error: GitlabHttpError = GitlabHttpError("denied", status)
    request_script.outcomes = [error]
    with pytest.raises(GitlabHttpError) as raised:
        bounded_client.http_request("GET", "/projects/example", retry_not_found=True)
    assert raised.value is error
    assert len(request_script.calls) == 1
    assert request_script.sleeps == []


def test_default_lookup_does_not_retry_missing_project(
    bounded_client: BoundedGitlabClient, request_script: RequestScript
) -> None:
    request_script.outcomes = [missing_project()]
    with pytest.raises(GitlabHttpError):
        bounded_client.http_request("GET", "/projects/example")
    assert len(request_script.calls) == 1
    assert request_script.sleeps == []


@pytest.mark.parametrize("verb", ["POST", "PUT", "PATCH", "DELETE"])
def test_missing_retry_rejected_for_writes(
    bounded_client: BoundedGitlabClient, request_script: RequestScript, verb: str
) -> None:
    with pytest.raises(ValueError, match="GET/HEAD"):
        bounded_client.http_request(verb, "/projects/example", retry_not_found=True)
    assert request_script.calls == []
    assert request_script.sleeps == []


@pytest.mark.parametrize(
    ("max_retries", "expected_sleeps"),
    [(0, []), (1, [1]), (3, [1, 2, 3]), (100, [1, 2, 3, 3])],
)
def test_missing_retry_obeys_request_budget_and_delay_cap(
    request_script: RequestScript, max_retries: int, expected_sleeps: list[float]
) -> None:
    request_script.outcomes = [missing_project() for _ in range(5)]
    client: BoundedGitlabClient = BoundedGitlabClient(
        "https://gitlab.invalid", private_token=uuid4().hex, max_delay=3
    )
    try:
        with pytest.raises(GitlabHttpError):
            client.http_request(
                "GET",
                "/projects/example",
                retry_not_found=True,
                max_retries=max_retries,
            )
        assert request_script.sleeps == expected_sleeps
        assert len(request_script.calls) == len(expected_sleeps) + 1
    finally:
        client.session.close()


def test_retry_logging_omits_credentials_paths_and_response_bodies(
    bounded_client: BoundedGitlabClient,
    request_script: RequestScript,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive: str = uuid4().hex
    request_script.outcomes = [
        GitlabHttpError(sensitive, HTTPStatus.NOT_FOUND, sensitive.encode()),
        None,
    ]
    with caplog.at_level(logging.WARNING, logger="speleodb.utils.gitlab_client"):
        bounded_client.http_request(
            "GET",
            f"https://oauth2:{sensitive}@gitlab.invalid/projects/{sensitive}",
            extra_headers={"PRIVATE-TOKEN": sensitive},
            retry_not_found=True,
        )
    assert "HTTP 404" in caplog.text
    assert sensitive not in caplog.text
    assert "gitlab.invalid" not in caplog.text


@pytest.fixture
def manager(bounded_client: BoundedGitlabClient) -> GitlabManagerCls:
    # Avoid changing the application singleton or its cached live client.
    instance: GitlabManagerCls = object.__new__(GitlabManagerCls)
    instance._gl = bounded_client  # noqa: SLF001
    return instance


@pytest.mark.parametrize("missing_count", [0, 1, 4])
def test_manager_existing_repository_never_creates(
    manager: GitlabManagerCls, request_script: RequestScript, missing_count: int
) -> None:
    request_script.outcomes = [missing_project() for _ in range(missing_count)] + [None]
    assert manager._ensure_remote_project(Project(id=uuid4())) is False  # noqa: SLF001
    assert [verb for verb, _, _ in request_script.calls] == ["get"] * (
        missing_count + 1
    )
    assert request_script.sleeps == [1, 2, 4, 8][:missing_count]


def test_manager_creates_only_after_all_missing_lookups(
    manager: GitlabManagerCls, request_script: RequestScript
) -> None:
    request_script.outcomes = [missing_project() for _ in range(5)] + [None]
    assert manager._ensure_remote_project(Project(id=uuid4())) is True  # noqa: SLF001
    assert [verb for verb, _, _ in request_script.calls] == ["get"] * 5 + ["post"]
    assert request_script.sleeps == [1, 2, 4, 8]


@pytest.mark.parametrize("status", [HTTPStatus.BAD_REQUEST, HTTPStatus.CONFLICT])
@pytest.mark.parametrize("recovery_succeeds", [True, False])
def test_manager_conflict_rechecks_without_another_creation(
    manager: GitlabManagerCls,
    request_script: RequestScript,
    status: HTTPStatus,
    recovery_succeeds: bool,
) -> None:
    body: bytes = b'{"base": ["path has already been taken"]}'
    request_script.outcomes = [missing_project() for _ in range(5)] + [
        GitlabHttpError("path has already been taken", status, body),
        *[missing_project() for _ in range(4)],
        None if recovery_succeeds else missing_project(),
    ]
    project: Project = Project(id=uuid4())
    if recovery_succeeds:
        assert manager._ensure_remote_project(project) is False  # noqa: SLF001
    else:
        with pytest.raises(GitlabCreateError) as raised:
            manager._ensure_remote_project(project)  # noqa: SLF001
        assert raised.value.response_code == status
        assert raised.value.response_body == body
        assert raised.value.error_message == "path has already been taken"
    assert [verb for verb, _, _ in request_script.calls] == (
        ["get"] * 5 + ["post"] + ["get"] * 5
    )
    assert request_script.sleeps == [1, 2, 4, 8] * 2


@pytest.mark.parametrize(
    ("status", "attempts"),
    [(HTTPStatus.FORBIDDEN, 1), (HTTPStatus.SERVICE_UNAVAILABLE, 5)],
)
def test_manager_failed_lookup_does_not_create_or_touch_checkout(
    manager: GitlabManagerCls,
    request_script: RequestScript,
    tmp_path: Path,
    status: HTTPStatus,
    attempts: int,
) -> None:
    project: Project = Project(id=uuid4())
    checkout: Path = tmp_path / str(project.id)
    checkout.mkdir()
    sentinel: Path = checkout / "existing-work"
    sentinel.write_text("preserved")
    request_script.outcomes = [GitlabHttpError("lookup failed", status)] * attempts
    with pytest.raises(GitlabGetError) as raised:
        manager.create_or_clone_project(project, tmp_path)
    assert raised.value.response_code == status
    assert [verb for verb, _, _ in request_script.calls] == ["get"] * attempts
    assert sentinel.read_text() == "preserved"


def test_manager_exhausted_network_failures_do_not_create(
    manager: GitlabManagerCls, request_script: RequestScript
) -> None:
    final_error: Timeout = Timeout("connection timed out")
    request_script.outcomes = [final_error] * 5
    with pytest.raises(Timeout) as raised:
        manager._ensure_remote_project(Project(id=uuid4()))  # noqa: SLF001
    assert raised.value is final_error
    assert [verb for verb, _, _ in request_script.calls] == ["get"] * 5
    assert request_script.sleeps == [1, 2, 4, 8]


def test_manager_conflict_followed_by_permission_failure_preserves_lookup_error(
    manager: GitlabManagerCls, request_script: RequestScript
) -> None:
    body: bytes = b"permission denied"
    request_script.outcomes = [
        *[missing_project() for _ in range(5)],
        GitlabHttpError("path taken", HTTPStatus.BAD_REQUEST),
        GitlabHttpError("permission denied", HTTPStatus.FORBIDDEN, body),
    ]
    with pytest.raises(GitlabGetError) as raised:
        manager._ensure_remote_project(Project(id=uuid4()))  # noqa: SLF001
    assert raised.value.response_code == HTTPStatus.FORBIDDEN
    assert raised.value.response_body == body
    assert [verb for verb, _, _ in request_script.calls] == ["get"] * 5 + [
        "post",
        "get",
    ]
    assert request_script.sleeps == [1, 2, 4, 8]
