"""Exercise fixture readiness retries through real HTTP and python-gitlab."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from typing import TYPE_CHECKING

import gitlab
import pytest
from requests.exceptions import ConnectionError as RequestConnectionError

from speleodb.background_jobs.tests.test_archive import INITIAL_COMMIT_ATTEMPTS
from speleodb.background_jobs.tests.test_archive import _create_initial_gitlab_commit

if TYPE_CHECKING:
    from collections.abc import Generator
    from collections.abc import Sequence

    from gitlab.v4.objects.projects import Project as GitlabProject


class CommitAPI(HTTPServer):
    def __init__(self) -> None:
        self.statuses: Sequence[HTTPStatus | None] = [HTTPStatus.CREATED]
        self.requests: list[tuple[str, bytes]] = []
        super().__init__(("127.0.0.1", 0), CommitHandler)


class CommitHandler(BaseHTTPRequestHandler):
    server: CommitAPI

    def do_POST(self) -> None:
        body: bytes = self.rfile.read(int(self.headers["Content-Length"]))
        self.server.requests.append((self.path, body))
        status: HTTPStatus | None = self.server.statuses[
            min(len(self.server.requests), len(self.server.statuses)) - 1
        ]
        if status is None:
            self.close_connection = True
            return
        payload: bytes = json.dumps(
            {"id": "initial-commit"}
            if status == HTTPStatus.CREATED
            else {"message": "initial commit rejected"}
        ).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        pass


@pytest.fixture
def commit_api() -> Generator[CommitAPI]:
    with CommitAPI() as server:
        thread: threading.Thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(timeout=5)


@pytest.fixture
def remote_project(commit_api: CommitAPI) -> Generator[GitlabProject]:
    client: gitlab.Gitlab = gitlab.Gitlab(
        f"http://127.0.0.1:{commit_api.server_port}",
        timeout=2,
    )
    try:
        yield client.projects.get(1, lazy=True)
    finally:
        client.session.close()


@pytest.mark.parametrize("not_found_responses", [0, 1, 2])
def test_initial_commit_waits_only_until_it_succeeds(
    commit_api: CommitAPI,
    remote_project: GitlabProject,
    not_found_responses: int,
) -> None:
    commit_api.statuses = [HTTPStatus.NOT_FOUND] * not_found_responses + [
        HTTPStatus.CREATED
    ]

    assert _create_initial_gitlab_commit(remote_project) == "initial-commit"

    assert len(commit_api.requests) == not_found_responses + 1
    assert len(set(commit_api.requests)) == 1
    path: str
    body: bytes
    path, body = commit_api.requests[0]
    assert path == "/api/v4/projects/1/repository/commits"
    assert json.loads(body) == {
        "branch": "main",
        "commit_message": "Historic survey",
        "actions": [
            {
                "action": "create",
                "file_path": "survey.txt",
                "content": "historic data",
            }
        ],
    }


def test_initial_commit_preserves_404_after_bounded_attempts(
    commit_api: CommitAPI, remote_project: GitlabProject
) -> None:
    commit_api.statuses = [HTTPStatus.NOT_FOUND]

    with pytest.raises(gitlab.exceptions.GitlabCreateError) as raised:
        _create_initial_gitlab_commit(remote_project)

    assert raised.value.response_code == HTTPStatus.NOT_FOUND
    assert raised.value.error_message == "initial commit rejected"
    assert len(commit_api.requests) == INITIAL_COMMIT_ATTEMPTS


@pytest.mark.parametrize(
    "status",
    [
        HTTPStatus.BAD_REQUEST,
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.CONFLICT,
        HTTPStatus.INTERNAL_SERVER_ERROR,
    ],
)
def test_initial_commit_does_not_replay_other_http_failures(
    commit_api: CommitAPI, remote_project: GitlabProject, status: HTTPStatus
) -> None:
    commit_api.statuses = [status, HTTPStatus.CREATED]

    with pytest.raises(gitlab.exceptions.GitlabError) as raised:
        _create_initial_gitlab_commit(remote_project)

    assert raised.value.response_code == status
    assert len(commit_api.requests) == 1


def test_initial_commit_does_not_replay_a_lost_response(
    commit_api: CommitAPI, remote_project: GitlabProject
) -> None:
    commit_api.statuses = [None, HTTPStatus.CREATED]

    with pytest.raises(RequestConnectionError):
        _create_initial_gitlab_commit(remote_project)

    assert len(commit_api.requests) == 1
