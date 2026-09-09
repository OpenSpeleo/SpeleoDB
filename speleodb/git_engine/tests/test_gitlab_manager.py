# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import tempfile
import uuid
from http import HTTPStatus
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import patch

import gitlab
import pytest
from django.conf import settings
from requests import Response
from requests.exceptions import Timeout

from speleodb.git_engine.client import GitlabClient
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager


class CreateOrCloneProjectTests(TestCase):
    def test_new_project_does_not_fetch_empty_remote(self) -> None:
        project = MagicMock()
        project.id = uuid.uuid4()
        git_repo = MagicMock(spec=GitRepo)
        origin = MagicMock()
        git_repo.create_remote.return_value = origin
        credentials = GitlabCredentials(
            instance="gitlab.example",
            token=uuid.uuid4().hex,
            group_id="1",
            group_name="test-group",
        )

        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(GitlabManager, "_gl", MagicMock()),
            patch.object(GitlabCredentials, "get", return_value=credentials),
            patch.object(GitlabManager, "create_project") as create_project,
            patch.object(GitRepo, "init", return_value=git_repo),
        ):
            result = GitlabManager.create_or_clone_project(
                project,
                base_dir=Path(temp_dir),
            )

        assert result is git_repo
        create_project.assert_called_once_with(project)
        git_repo.create_remote.assert_called_once()
        origin.fetch.assert_not_called()
        git_repo.publish_first_commit.assert_called_once_with()


def gitlab_response(
    status: HTTPStatus, message: str = "", *, retry_after: str | None = None
) -> Response:
    response: Response = Response()
    response.status_code = status
    response.reason = status.phrase
    response.url = "https://gitlab.example/api/v4/projects"
    response.headers["Content-Type"] = "application/json"
    response._content = json.dumps(  # noqa: SLF001
        {"message": message} if message else {"id": 1}
    ).encode()
    if retry_after is not None:
        response.headers["Retry-After"] = retry_after
    return response


class ProjectCreationFailureTests(TestCase):
    """Exercise the real python-gitlab retry and HTTP error mapping."""

    def setUp(self) -> None:
        super().setUp()
        self.project: MagicMock = MagicMock(id=uuid.uuid4())
        self.credentials: GitlabCredentials = GitlabCredentials(
            instance="gitlab.example",
            token=uuid.uuid4().hex,
            group_id="1",
            group_name="test-group",
        )
        self.client: GitlabClient = GitlabClient(
            "https://gitlab.example", private_token=self.credentials.token
        )
        self.addCleanup(self.client.session.close)
        self.enterContext(patch.object(GitlabManager, "_gl", self.client))
        self.enterContext(
            patch.object(GitlabCredentials, "get", return_value=self.credentials)
        )
        self.base_dir: Path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.repo: MagicMock = MagicMock(spec=GitRepo)
        self.init: MagicMock = self.enterContext(
            patch.object(GitRepo, "init", return_value=self.repo)
        )
        self.clone: MagicMock = self.enterContext(
            patch.object(GitRepo, "clone_from", return_value=self.repo)
        )
        self.sleep: MagicMock = self.enterContext(patch("gitlab.utils.time.sleep"))

    def create_or_clone(self) -> GitRepo | None:
        return GitlabManager.create_or_clone_project(self.project, self.base_dir)

    def test_transient_create_failure_recovers(self) -> None:
        for status in (
            HTTPStatus.TOO_MANY_REQUESTS,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPStatus.BAD_GATEWAY,
            HTTPStatus.SERVICE_UNAVAILABLE,
            HTTPStatus.GATEWAY_TIMEOUT,
        ):
            with (
                self.subTest(status=status),
                patch.object(
                    self.client.session,
                    "send",
                    side_effect=[
                        gitlab_response(status, "temporary failure"),
                        gitlab_response(HTTPStatus.CREATED),
                    ],
                ) as send,
            ):
                self.sleep.reset_mock()
                assert self.create_or_clone() is self.repo
                assert send.call_count == 2  # noqa: PLR2004
                self.sleep.assert_called_once()
        self.clone.assert_not_called()

    def test_rate_limit_honors_retry_after(self) -> None:
        with patch.object(
            self.client.session,
            "send",
            side_effect=[
                gitlab_response(
                    HTTPStatus.TOO_MANY_REQUESTS, "rate limit", retry_after="3"
                ),
                gitlab_response(HTTPStatus.CREATED),
            ],
        ):
            assert self.create_or_clone() is self.repo
        self.sleep.assert_called_once_with(3)
        self.clone.assert_not_called()

    def test_create_timeout_recovers(self) -> None:
        with patch.object(
            self.client.session,
            "send",
            side_effect=[
                Timeout("temporary timeout"),
                gitlab_response(HTTPStatus.CREATED),
            ],
        ):
            assert self.create_or_clone() is self.repo
        self.sleep.assert_called_once()
        self.clone.assert_not_called()

    def test_failed_creation_never_attempts_clone(self) -> None:
        for status in (
            HTTPStatus.FORBIDDEN,
            HTTPStatus.TOO_MANY_REQUESTS,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPStatus.BAD_GATEWAY,
            HTTPStatus.SERVICE_UNAVAILABLE,
            HTTPStatus.GATEWAY_TIMEOUT,
        ):
            with (
                self.subTest(status=status),
                patch.object(
                    self.client.session,
                    "send",
                    return_value=gitlab_response(status, "original create failure"),
                ) as send,
                pytest.raises(gitlab.exceptions.GitlabCreateError) as raised,
            ):
                self.create_or_clone()
            assert raised.value.response_code == status
            assert "original create failure" in str(raised.value)
            expected_attempts: int = (
                1
                if status == HTTPStatus.FORBIDDEN
                else settings.DJANGO_GIT_RETRY_ATTEMPTS
            )
            assert send.call_count == expected_attempts
        self.clone.assert_not_called()
        self.init.assert_not_called()

    def test_authentication_failure_is_not_retried(self) -> None:
        with (
            patch.object(
                self.client.session,
                "send",
                return_value=gitlab_response(HTTPStatus.UNAUTHORIZED, "invalid token"),
            ) as send,
            pytest.raises(gitlab.exceptions.GitlabAuthenticationError),
        ):
            self.create_or_clone()
        send.assert_called_once()
        self.sleep.assert_not_called()
        self.clone.assert_not_called()

    def test_conflict_requires_confirmed_existing_repository(self) -> None:
        for status in (HTTPStatus.BAD_REQUEST, HTTPStatus.CONFLICT):
            with (
                self.subTest(status=status),
                patch.object(
                    self.client.session,
                    "send",
                    side_effect=[
                        gitlab_response(status, "path already taken"),
                        gitlab_response(HTTPStatus.OK),
                    ],
                ) as send,
            ):
                self.clone.reset_mock()
                assert self.create_or_clone() is self.repo
                assert [call.args[0].method for call in send.call_args_list] == [
                    "POST",
                    "GET",
                ]
                assert (
                    send.call_args_list[-1]
                    .args[0]
                    .url.endswith(f"/projects/test-group%2F{self.project.id}")
                )
                self.clone.assert_called_once()
        self.init.assert_not_called()
        self.repo.publish_first_commit.assert_not_called()

    def test_invalid_create_preserves_error_when_repository_is_absent(self) -> None:
        for status in (HTTPStatus.BAD_REQUEST, HTTPStatus.CONFLICT):
            with (
                self.subTest(status=status),
                patch.object(
                    self.client.session,
                    "send",
                    side_effect=[
                        gitlab_response(status, "original validation failure"),
                        gitlab_response(HTTPStatus.NOT_FOUND, "not found"),
                    ],
                ),
                pytest.raises(gitlab.exceptions.GitlabCreateError) as raised,
            ):
                self.create_or_clone()
            assert raised.value.response_code == status
            assert "original validation failure" in str(raised.value)
        self.clone.assert_not_called()

    def test_conflict_lookup_retries_transient_failure(self) -> None:
        with patch.object(
            self.client.session,
            "send",
            side_effect=[
                gitlab_response(HTTPStatus.BAD_REQUEST, "path already taken"),
                gitlab_response(HTTPStatus.SERVICE_UNAVAILABLE, "temporary failure"),
                gitlab_response(HTTPStatus.OK),
            ],
        ):
            assert self.create_or_clone() is self.repo
        self.sleep.assert_called_once()
        self.clone.assert_called_once()

    def test_create_retry_can_recover_as_confirmed_duplicate(self) -> None:
        # A failed response can arrive after GitLab created the repository.
        with patch.object(
            self.client.session,
            "send",
            side_effect=[
                gitlab_response(HTTPStatus.BAD_GATEWAY, "response lost"),
                gitlab_response(HTTPStatus.BAD_REQUEST, "path already taken"),
                gitlab_response(HTTPStatus.OK),
            ],
        ):
            assert self.create_or_clone() is self.repo
        self.sleep.assert_called_once()
        self.clone.assert_called_once()
        self.init.assert_not_called()

    def test_conflict_lookup_failure_does_not_clone(self) -> None:
        with (
            patch.object(
                self.client.session,
                "send",
                side_effect=[
                    gitlab_response(HTTPStatus.BAD_REQUEST, "path already taken"),
                    *[
                        gitlab_response(HTTPStatus.SERVICE_UNAVAILABLE, "lookup failed")
                        for _ in range(settings.DJANGO_GIT_RETRY_ATTEMPTS)
                    ],
                ],
            ),
            pytest.raises(gitlab.exceptions.GitlabGetError) as raised,
        ):
            self.create_or_clone()
        assert raised.value.response_code == HTTPStatus.SERVICE_UNAVAILABLE
        self.clone.assert_not_called()

    def test_confirmed_empty_repository_gets_initial_commit(self) -> None:
        self.repo.head.is_valid.return_value = False
        with patch.object(
            self.client.session,
            "send",
            side_effect=[
                gitlab_response(HTTPStatus.BAD_REQUEST, "path already taken"),
                gitlab_response(HTTPStatus.OK),
            ],
        ):
            assert self.create_or_clone() is self.repo
        self.repo.publish_first_commit.assert_called_once_with()
