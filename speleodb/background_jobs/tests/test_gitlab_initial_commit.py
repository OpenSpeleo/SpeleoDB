"""Verify fixture readiness against the real authenticated GitLab service."""

from __future__ import annotations

import socket
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any
from uuid import uuid4

import gitlab
import pytest
from django.conf import settings
from requests.exceptions import ConnectionError as RequestConnectionError

from speleodb.background_jobs.tests.test_archive import INITIAL_COMMIT_ATTEMPTS
from speleodb.background_jobs.tests.test_archive import _create_initial_gitlab_commit
from speleodb.git_engine.tests.live_gitlab import (
    configured_gitlab_fixture,  # noqa: F401
)
from speleodb.git_engine.tests.live_gitlab import (
    disposable_project_fixture,  # noqa: F401
)
from speleodb.utils.gitlab_client import BoundedGitlabClient

if TYPE_CHECKING:
    from collections.abc import Generator

    from gitlab.v4.objects.projects import Project as GitlabProject
    from requests import Response

    from speleodb.surveys.models import Project

pytestmark = pytest.mark.skip_if_lighttest


@pytest.fixture
def remote_project(
    live_gitlab: gitlab.Gitlab,
    live_project: Project,
) -> GitlabProject:
    return live_gitlab.projects.create(
        {"name": str(live_project.id), "namespace_id": settings.GITLAB_GROUP_ID}
    )


@pytest.fixture
def commit_responses(live_gitlab: gitlab.Gitlab) -> Generator[list[Response]]:
    """Observe real commit responses using Requests' supported response hook."""
    responses: list[Response] = []

    def observe(response: Response, **kwargs: Any) -> None:
        if response.request.method == "POST" and response.request.path_url.endswith(
            "/repository/commits"
        ):
            responses.append(response)

    live_gitlab.session.hooks["response"].append(observe)
    try:
        yield responses
    finally:
        live_gitlab.session.hooks["response"].remove(observe)


def test_initial_commit_creates_expected_remote_content(
    remote_project: GitlabProject,
    commit_responses: list[Response],
) -> None:
    initial_sha: str = _create_initial_gitlab_commit(remote_project)

    assert 1 <= len(commit_responses) <= INITIAL_COMMIT_ATTEMPTS
    assert commit_responses[-1].status_code == HTTPStatus.CREATED
    assert all(
        response.status_code == HTTPStatus.NOT_FOUND
        for response in commit_responses[:-1]
    )
    assert all(
        "PRIVATE-TOKEN" in response.request.headers for response in commit_responses
    )
    initial = remote_project.commits.get(initial_sha)
    assert initial.message.strip() == "Historic survey"
    assert remote_project.branches.get("main").commit["id"] == initial_sha
    assert remote_project.files.get("survey.txt", ref=initial_sha).decode() == (
        b"historic data"
    )
    assert len(remote_project.commits.list(get_all=True)) == 1


def test_initial_commit_preserves_404_after_bounded_attempts(
    live_gitlab: gitlab.Gitlab,
    commit_responses: list[Response],
) -> None:
    missing: GitlabProject = live_gitlab.projects.get(
        f"{settings.GITLAB_GROUP_NAME}/missing-{uuid4()}", lazy=True
    )
    with pytest.raises(gitlab.exceptions.GitlabCreateError) as raised:
        _create_initial_gitlab_commit(missing)

    assert raised.value.response_code == HTTPStatus.NOT_FOUND
    assert len(commit_responses) == INITIAL_COMMIT_ATTEMPTS
    assert all(
        response.status_code == HTTPStatus.NOT_FOUND for response in commit_responses
    )


def test_initial_commit_preserves_duplicate_file_error(
    remote_project: GitlabProject,
    commit_responses: list[Response],
) -> None:
    initial_sha: str = _create_initial_gitlab_commit(remote_project)
    commit_responses.clear()

    with pytest.raises(gitlab.exceptions.GitlabCreateError) as raised:
        _create_initial_gitlab_commit(remote_project)

    assert raised.value.response_code == HTTPStatus.BAD_REQUEST
    assert len(commit_responses) == 1
    assert "already exists" in str(raised.value.error_message).lower()
    assert [commit.id for commit in remote_project.commits.list(get_all=True)] == [
        initial_sha
    ]


def test_initial_commit_preserves_invalid_token_error(
    remote_project: GitlabProject,
) -> None:
    # Successful authenticated setup prevents an outage from satisfying this test.
    client: gitlab.Gitlab = BoundedGitlabClient(
        f"{settings.GITLAB_HTTP_PROTOCOL}://{settings.GITLAB_HOST_URL}",
        private_token=f"invalid-{uuid4()}",
        timeout=2,
        max_attempts=1,
    )
    try:
        project: GitlabProject = client.projects.get(remote_project.id, lazy=True)
        with pytest.raises(gitlab.exceptions.GitlabAuthenticationError) as raised:
            _create_initial_gitlab_commit(project)
        assert raised.value.response_code == HTTPStatus.UNAUTHORIZED
    finally:
        client.session.close()


def test_initial_commit_preserves_connection_refusal() -> None:
    # Bind without listening: the OS refuses the real HTTP connection. No
    # application server or fabricated HTTP response participates in this test.
    with socket.socket() as unavailable:
        unavailable.bind(("127.0.0.1", 0))
        client: gitlab.Gitlab = BoundedGitlabClient(
            f"http://127.0.0.1:{unavailable.getsockname()[1]}",
            private_token=f"unreachable-{uuid4()}",
            timeout=2,
            max_attempts=1,
        )
        try:
            project: GitlabProject = client.projects.get(1, lazy=True)
            with pytest.raises(RequestConnectionError):
                _create_initial_gitlab_commit(project)
        finally:
            client.session.close()
