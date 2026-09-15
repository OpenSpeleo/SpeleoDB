# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import uuid
from contextvars import Context
from http import HTTPStatus
from typing import Any
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import patch

import gitlab.exceptions
import pytest
from django.conf import settings
from requests import Response
from requests.exceptions import ChunkedEncodingError
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout

from speleodb.git_engine.client import GitlabClient
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.surveys.models import Project
from speleodb.utils.gitlab_client import BoundedGitlabClient

API_URL = "https://gitlab.example"
HTTP_TIMEOUT_SECONDS = 30
PROJECT_NUMERIC_ID = 17
TEST_GROUP = "test-group"
TEST_TOKEN = uuid.uuid4().hex
USER_COMMIT_SHA = "a" * 40


def gitlab_response(status: HTTPStatus, payload: Any | None = None) -> Response:
    """Build a requests response consumed by python-gitlab's real SDK paths."""
    response = Response()
    response.status_code = status
    response.reason = status.phrase
    response.url = f"{API_URL}/api/v4/projects"
    response.headers["Content-Type"] = "application/json"
    if isinstance(payload, list):
        response.headers.update(
            {
                "X-Page": "1",
                "X-Per-Page": str(max(len(payload), 1)),
                "X-Next-Page": "",
                "X-Total": str(len(payload)),
                "X-Total-Pages": "1",
            }
        )
    if payload is None:
        payload = {"message": status.phrase} if status >= HTTPStatus.BAD_REQUEST else {}
    response._content = json.dumps(payload).encode()  # noqa: SLF001
    return response


def project_payload(
    project: Project,
    numeric_id: int = PROJECT_NUMERIC_ID,
) -> dict[str, Any]:
    return {
        "id": numeric_id,
        "name": str(project.id),
        "path": str(project.id),
        "path_with_namespace": f"{TEST_GROUP}/{project.id}",
    }


def commit_payload() -> dict[str, Any]:
    return {
        "id": USER_COMMIT_SHA,
        "message": "User commit",
        "web_url": f"{API_URL}/{TEST_GROUP}/project/-/commit/{USER_COMMIT_SHA}",
    }


class GitlabClientPolicyTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client = GitlabClient(API_URL, private_token=TEST_TOKEN)
        self.addCleanup(self.client.session.close)
        self.sleep: MagicMock = self.enterContext(
            patch("speleodb.utils.gitlab_client.time.sleep")
        )

    def test_get_and_head_retry_transient_failures_with_fixed_timeout(self) -> None:
        for verb in ("GET", "HEAD"):
            with (
                self.subTest(verb=verb),
                patch.object(
                    self.client.session,
                    "send",
                    side_effect=[
                        gitlab_response(HTTPStatus.SERVICE_UNAVAILABLE),
                        gitlab_response(HTTPStatus.OK),
                    ],
                ) as send,
            ):
                self.sleep.reset_mock()
                response = self.client.http_request(verb, "/version")

                assert response.status_code == HTTPStatus.OK
                assert send.call_count == 2  # noqa: PLR2004
                assert all(
                    request.kwargs["timeout"] == HTTP_TIMEOUT_SECONDS
                    for request in send.call_args_list
                )
                self.sleep.assert_called_once()

    def test_read_timeout_recovers_and_exhaustion_is_bounded(self) -> None:
        with patch.object(
            self.client.session,
            "send",
            side_effect=[
                Timeout("temporary timeout"),
                gitlab_response(HTTPStatus.OK),
            ],
        ) as send:
            assert self.client.http_request("GET", "/version").ok
            assert send.call_count == 2  # noqa: PLR2004

        self.sleep.reset_mock()
        with (
            patch.object(
                self.client.session,
                "send",
                side_effect=Timeout("persistent timeout"),
            ) as send,
            pytest.raises(Timeout, match="persistent timeout"),
        ):
            self.client.http_request("GET", "/version")

        assert send.call_count == settings.DJANGO_GIT_RETRY_ATTEMPTS
        assert self.sleep.call_count == settings.DJANGO_GIT_RETRY_ATTEMPTS - 1

    def test_writes_retry_only_with_explicit_opt_in(self) -> None:
        with (
            patch.object(
                self.client.session,
                "send",
                return_value=gitlab_response(HTTPStatus.SERVICE_UNAVAILABLE),
            ) as send,
            pytest.raises(gitlab.exceptions.GitlabHttpError),
        ):
            self.client.http_request("POST", "/projects", post_data={"name": "p"})
        send.assert_called_once()

        with patch.object(
            self.client.session,
            "send",
            side_effect=[
                gitlab_response(HTTPStatus.SERVICE_UNAVAILABLE),
                gitlab_response(HTTPStatus.CREATED),
            ],
        ) as send:
            response = self.client.http_request(
                "POST",
                "/projects",
                post_data={"name": "p"},
                retry_transient_errors=True,
            )

        assert response.status_code == HTTPStatus.CREATED
        assert send.call_count == 2  # noqa: PLR2004

    def test_resource_lock_conflicts_keep_the_sdk_transient_retry_policy(self) -> None:
        for verb, explicit_retry in (("GET", None), ("HEAD", None), ("POST", True)):
            locked: Response = gitlab_response(HTTPStatus.CONFLICT)
            locked.reason = "Resource lock"
            with (
                self.subTest(verb=verb),
                patch.object(
                    self.client.session.get_adapter(API_URL),
                    "send",
                    side_effect=[locked, gitlab_response(HTTPStatus.OK)],
                ) as send,
            ):
                self.sleep.reset_mock()
                response: Response = self.client.http_request(
                    verb, "/version", retry_transient_errors=explicit_retry
                )

            assert response.ok
            assert send.call_count == 2  # noqa: PLR2004
            self.sleep.assert_called_once_with(1.0)

    def test_resource_lock_classification_does_not_retry_other_conflicts(self) -> None:
        for reason, verb, explicit_retry in (
            ("Conflict", "GET", None),
            ("Resource lock", "GET", False),
            ("Resource lock", "POST", None),
        ):
            conflict: Response = gitlab_response(HTTPStatus.CONFLICT)
            conflict.reason = reason
            with (
                self.subTest(reason=reason, verb=verb, retry=explicit_retry),
                patch.object(
                    self.client.session.get_adapter(API_URL),
                    "send",
                    return_value=conflict,
                ) as send,
                pytest.raises(gitlab.exceptions.GitlabHttpError) as raised,
            ):
                self.client.http_request(
                    verb, "/version", retry_transient_errors=explicit_retry
                )

            assert raised.value.response_code == HTTPStatus.CONFLICT
            send.assert_called_once()
        self.sleep.assert_not_called()

    def test_resource_lock_classification_is_reset_for_the_next_attempt(self) -> None:
        locked: Response = gitlab_response(HTTPStatus.CONFLICT)
        locked.reason = "Resource lock"
        ordinary: Response = gitlab_response(HTTPStatus.CONFLICT)
        with (
            patch.object(
                self.client.session.get_adapter(API_URL),
                "send",
                side_effect=[locked, ordinary],
            ) as send,
            pytest.raises(gitlab.exceptions.GitlabHttpError) as raised,
        ):
            self.client.http_request("GET", "/version")

        assert raised.value.response_code == HTTPStatus.CONFLICT
        assert send.call_count == 2  # noqa: PLR2004
        self.sleep.assert_called_once_with(1.0)

    def test_resource_lock_classification_is_isolated_between_contexts(self) -> None:
        isolated: Context = Context()
        locked: Response = gitlab_response(HTTPStatus.CONFLICT)
        locked.reason = "Resource lock"

        def interleave_request(response: Response, **kwargs: Any) -> None:
            if response is locked:
                with pytest.raises(gitlab.exceptions.GitlabHttpError) as raised:
                    isolated.run(self.client.http_request, "GET", "/other-request")
                assert raised.value.response_code == HTTPStatus.CONFLICT

        self.client.session.hooks["response"].append(interleave_request)
        with patch.object(
            self.client.session.get_adapter(API_URL),
            "send",
            side_effect=[
                locked,
                gitlab_response(HTTPStatus.CONFLICT),
                gitlab_response(HTTPStatus.OK),
            ],
        ) as send:
            response: Response = self.client.http_request("GET", "/version")

        assert response.ok
        assert send.call_count == 3  # noqa: PLR2004
        self.sleep.assert_called_once_with(1.0)

    def test_retry_override_cannot_remove_or_expand_the_attempt_limit(self) -> None:
        with (
            patch.object(self.client.session, "send") as send,
            pytest.raises(ValueError, match="max_retries"),
        ):
            self.client.http_request("GET", "/version", max_retries=-1)
        send.assert_not_called()
        self.sleep.assert_not_called()

        for max_retries, expected_attempts in (
            (0, 1),
            (1, 2),
            (1_000_000, settings.DJANGO_GIT_RETRY_ATTEMPTS),
        ):
            self.sleep.reset_mock()
            with (
                self.subTest(max_retries=max_retries),
                patch.object(
                    self.client.session,
                    "send",
                    return_value=gitlab_response(HTTPStatus.SERVICE_UNAVAILABLE),
                ) as send,
                pytest.raises(gitlab.exceptions.GitlabHttpError),
            ):
                self.client.http_request("GET", "/version", max_retries=max_retries)
            assert send.call_count == expected_attempts
            assert self.sleep.call_count == expected_attempts - 1

    def test_timeout_override_must_be_finite_and_positive(self) -> None:
        for timeout in (float("inf"), float("-inf"), float("nan"), 0.0, -1.0):
            with (
                self.subTest(timeout=timeout),
                patch.object(self.client.session, "send") as send,
                pytest.raises(ValueError, match="timeout"),
            ):
                self.client.http_request("GET", "/version", timeout=timeout)
            send.assert_not_called()
        self.sleep.assert_not_called()

    def test_timeout_override_can_only_reduce_the_configured_limit(self) -> None:
        for timeout, expected_timeout in (
            (0.5, 0.5),
            (3600.0, HTTP_TIMEOUT_SECONDS),
        ):
            with (
                self.subTest(timeout=timeout),
                patch.object(
                    self.client.session,
                    "send",
                    return_value=gitlab_response(HTTPStatus.OK),
                ) as send,
            ):
                self.client.http_request("GET", "/version", timeout=timeout)
            assert send.call_args.kwargs["timeout"] == expected_timeout

    def test_transport_failures_follow_the_read_and_write_policy(self) -> None:
        for exception_type in (RequestsConnectionError, ChunkedEncodingError, Timeout):
            for verb, explicit_retry, expected_attempts in (
                ("GET", None, settings.DJANGO_GIT_RETRY_ATTEMPTS),
                ("HEAD", None, settings.DJANGO_GIT_RETRY_ATTEMPTS),
                ("GET", False, 1),
                ("POST", None, 1),
                ("POST", True, settings.DJANGO_GIT_RETRY_ATTEMPTS),
            ):
                failure = exception_type("original transport failure")
                self.sleep.reset_mock()
                with (
                    self.subTest(
                        exception=exception_type, verb=verb, retry=explicit_retry
                    ),
                    patch.object(
                        self.client.session, "send", side_effect=failure
                    ) as send,
                    pytest.raises(exception_type) as raised,
                ):
                    self.client.http_request(
                        verb,
                        "/version",
                        retry_transient_errors=explicit_retry,
                    )
                assert raised.value is failure
                assert send.call_count == expected_attempts
                expected_delays = [1.0, 2.0, 4.0, 8.0][: expected_attempts - 1]
                actual_delays = [call.args[0] for call in self.sleep.call_args_list]
                assert actual_delays == expected_delays

    def test_rate_limit_retry_can_be_disabled(self) -> None:
        with (
            patch.object(
                self.client.session,
                "send",
                return_value=gitlab_response(HTTPStatus.TOO_MANY_REQUESTS),
            ) as send,
            pytest.raises(gitlab.exceptions.GitlabHttpError),
        ):
            self.client.http_request("GET", "/version", obey_rate_limit=False)
        send.assert_called_once()
        self.sleep.assert_not_called()

    def test_read_error_preserves_status_message_and_exact_response_body(self) -> None:
        for status, expected_attempts in (
            (HTTPStatus.FORBIDDEN, 1),
            (HTTPStatus.NOT_FOUND, 1),
            (HTTPStatus.SERVICE_UNAVAILABLE, settings.DJANGO_GIT_RETRY_ATTEMPTS),
        ):
            response = gitlab_response(status, {"message": "original read failure"})
            self.sleep.reset_mock()
            with (
                self.subTest(status=status),
                patch.object(
                    self.client.session, "send", return_value=response
                ) as send,
                pytest.raises(gitlab.exceptions.GitlabGetError) as raised,
            ):
                self.client.projects.get(PROJECT_NUMERIC_ID)
            assert send.call_count == expected_attempts
            assert self.sleep.call_count == expected_attempts - 1
            assert raised.value.response_code == status
            assert raised.value.error_message == "original read failure"
            assert raised.value.response_body == response.content

    def test_longer_finite_budget_caps_exponential_delay(self) -> None:
        max_attempts = 8
        client = BoundedGitlabClient(
            API_URL, private_token=TEST_TOKEN, max_attempts=max_attempts
        )
        self.addCleanup(client.session.close)
        with (
            patch.object(
                client.session,
                "send",
                return_value=gitlab_response(HTTPStatus.SERVICE_UNAVAILABLE),
            ) as send,
            pytest.raises(gitlab.exceptions.GitlabHttpError),
        ):
            client.http_request("GET", "/version")
        assert send.call_count == max_attempts
        assert [call.args[0] for call in self.sleep.call_args_list] == [
            1.0,
            2.0,
            4.0,
            8.0,
            16.0,
            30.0,
            30.0,
        ]

    def test_invalid_constructor_budgets_are_rejected(self) -> None:
        for max_attempts in (0, -1):
            with (
                self.subTest(max_attempts=max_attempts),
                pytest.raises(ValueError, match="max_attempts"),
            ):
                BoundedGitlabClient(
                    API_URL, private_token=TEST_TOKEN, max_attempts=max_attempts
                )
        for field in ("timeout", "base_delay", "max_delay"):
            for value in (float("inf"), float("nan"), 0.0, -1.0):
                invalid_options: dict[str, Any] = {field: value}
                with (
                    self.subTest(field=field, value=value),
                    pytest.raises(ValueError, match="finite and positive"),
                ):
                    BoundedGitlabClient(
                        API_URL, private_token=TEST_TOKEN, **invalid_options
                    )


class GitlabManagerReadPolicyTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.credentials = GitlabCredentials(
            instance="gitlab.example",
            token=TEST_TOKEN,
            group_id="1",
            group_name=TEST_GROUP,
        )
        self.client = GitlabClient(API_URL, private_token=TEST_TOKEN)
        self.addCleanup(self.client.session.close)
        self.project = Project(id=uuid.uuid4())
        GitlabManager._get_project.cache_clear()  # noqa: SLF001
        self.addCleanup(GitlabManager._get_project.cache_clear)  # noqa: SLF001
        self.enterContext(patch.object(GitlabManager, "_gl", self.client))
        self.enterContext(
            patch.object(GitlabCredentials, "get", return_value=self.credentials)
        )
        self.sleep: MagicMock = self.enterContext(
            patch("speleodb.utils.gitlab_client.time.sleep")
        )

    def test_failed_auth_reinitialization_clears_cache_and_client(self) -> None:
        with patch.object(
            self.client.session,
            "send",
            return_value=gitlab_response(
                HTTPStatus.OK,
                project_payload(self.project),
            ),
        ):
            GitlabManager._get_project(self.project)  # noqa: SLF001
        assert GitlabManager._get_project.cache_info().currsize == 1  # noqa: SLF001

        replacement = GitlabClient(API_URL, private_token=TEST_TOKEN)
        self.addCleanup(replacement.session.close)
        with (
            patch(
                "speleodb.git_engine.gitlab_manager.GitlabClient",
                return_value=replacement,
            ),
            patch.object(
                replacement.session,
                "send",
                return_value=gitlab_response(
                    HTTPStatus.UNAUTHORIZED,
                    {"message": "invalid token"},
                ),
            ) as send,
            patch.object(replacement.session, "close") as close,
            pytest.raises(gitlab.exceptions.GitlabAuthenticationError),
        ):
            GitlabManager._initialize()  # noqa: SLF001

        send.assert_called_once()
        close.assert_called_once_with()
        assert GitlabManager._gl is None  # noqa: SLF001
        assert GitlabManager._get_project.cache_info().currsize == 0  # noqa: SLF001

    def test_auth_read_retries_then_recovers(self) -> None:
        replacement = GitlabClient(API_URL, private_token=TEST_TOKEN)
        self.addCleanup(replacement.session.close)
        with (
            patch(
                "speleodb.git_engine.gitlab_manager.GitlabClient",
                return_value=replacement,
            ),
            patch.object(
                replacement.session,
                "send",
                side_effect=[
                    gitlab_response(HTTPStatus.SERVICE_UNAVAILABLE),
                    gitlab_response(
                        HTTPStatus.OK,
                        {"id": 1, "username": "test-user"},
                    ),
                ],
            ) as send,
        ):
            GitlabManager._initialize()  # noqa: SLF001

        assert GitlabManager._gl is replacement  # noqa: SLF001
        assert send.call_count == 2  # noqa: PLR2004
        self.sleep.assert_called_once()

    def test_auth_read_exhaustion_leaves_manager_uninitialized(self) -> None:
        replacement = GitlabClient(API_URL, private_token=TEST_TOKEN)
        self.addCleanup(replacement.session.close)
        with (
            patch(
                "speleodb.git_engine.gitlab_manager.GitlabClient",
                return_value=replacement,
            ),
            patch.object(
                replacement.session,
                "send",
                return_value=gitlab_response(HTTPStatus.SERVICE_UNAVAILABLE),
            ) as send,
            patch.object(replacement.session, "close") as close,
            pytest.raises(gitlab.exceptions.GitlabGetError),
        ):
            GitlabManager._initialize()  # noqa: SLF001

        assert send.call_count == settings.DJANGO_GIT_RETRY_ATTEMPTS
        close.assert_called_once_with()
        assert GitlabManager._gl is None  # noqa: SLF001

    def test_cached_project_does_not_bypass_branch_reauthentication(self) -> None:
        with patch.object(
            self.client.session,
            "send",
            return_value=gitlab_response(
                HTTPStatus.OK,
                project_payload(self.project),
            ),
        ):
            GitlabManager._get_project(self.project)  # noqa: SLF001

        replacement = GitlabClient(API_URL, private_token=TEST_TOKEN)
        self.addCleanup(replacement.session.close)
        GitlabManager._gl = None  # noqa: SLF001
        with (
            patch(
                "speleodb.git_engine.gitlab_manager.GitlabClient",
                return_value=replacement,
            ),
            patch.object(
                replacement.session,
                "send",
                side_effect=[
                    gitlab_response(
                        HTTPStatus.OK,
                        {"id": 1, "username": "test-user"},
                    ),
                    gitlab_response(
                        HTTPStatus.OK,
                        project_payload(self.project),
                    ),
                    gitlab_response(
                        HTTPStatus.OK,
                        {
                            "name": settings.DJANGO_GIT_BRANCH_NAME,
                            "commit": {"id": USER_COMMIT_SHA},
                        },
                    ),
                ],
            ) as send,
        ):
            assert GitlabManager.get_last_commit_hash(self.project) == USER_COMMIT_SHA

        assert GitlabManager._gl is replacement  # noqa: SLF001
        assert send.call_count == 3  # noqa: PLR2004

    def test_project_404_is_not_cached(self) -> None:
        with patch.object(
            self.client.session,
            "send",
            side_effect=[
                gitlab_response(HTTPStatus.NOT_FOUND),
                gitlab_response(HTTPStatus.OK, project_payload(self.project)),
                gitlab_response(HTTPStatus.OK, [commit_payload()]),
            ],
        ) as send:
            assert GitlabManager.get_commit_history(self.project) is None
            assert GitlabManager.get_commit_history(self.project) == [
                {"id": USER_COMMIT_SHA, "message": "User commit"}
            ]

        assert send.call_count == 3  # noqa: PLR2004

    def test_commit_list_retries_and_propagates_exhaustion(self) -> None:
        with patch.object(
            self.client.session,
            "send",
            side_effect=[
                gitlab_response(HTTPStatus.OK, project_payload(self.project)),
                gitlab_response(HTTPStatus.SERVICE_UNAVAILABLE),
                gitlab_response(HTTPStatus.OK, [commit_payload()]),
            ],
        ) as send:
            assert GitlabManager.get_commit_history(self.project) == [
                {"id": USER_COMMIT_SHA, "message": "User commit"}
            ]
        assert send.call_count == 3  # noqa: PLR2004

        second_project = Project(id=uuid.uuid4())
        self.sleep.reset_mock()
        with (
            patch.object(
                self.client.session,
                "send",
                side_effect=[
                    gitlab_response(HTTPStatus.OK, project_payload(second_project)),
                    *[
                        gitlab_response(HTTPStatus.SERVICE_UNAVAILABLE)
                        for _ in range(settings.DJANGO_GIT_RETRY_ATTEMPTS)
                    ],
                ],
            ) as send,
            pytest.raises(gitlab.exceptions.GitlabListError),
        ):
            GitlabManager.get_commit_history(second_project)

        assert send.call_count == settings.DJANGO_GIT_RETRY_ATTEMPTS + 1

    def test_commit_list_404_is_empty_but_outage_is_not(self) -> None:
        with patch.object(
            self.client.session,
            "send",
            side_effect=[
                gitlab_response(HTTPStatus.OK, project_payload(self.project)),
                gitlab_response(HTTPStatus.NOT_FOUND),
            ],
        ):
            assert GitlabManager.get_commit_history(self.project) is None

        replacement_numeric_id = PROJECT_NUMERIC_ID + 1
        with patch.object(
            self.client.session,
            "send",
            side_effect=[
                gitlab_response(
                    HTTPStatus.OK,
                    project_payload(self.project, replacement_numeric_id),
                ),
                gitlab_response(HTTPStatus.OK, [commit_payload()]),
            ],
        ) as send:
            assert GitlabManager.get_commit_history(self.project) == [
                {"id": USER_COMMIT_SHA, "message": "User commit"}
            ]
        assert (
            f"/projects/{replacement_numeric_id}/repository/commits"
            in send.call_args_list[-1].args[0].url
        )

        second_project = Project(id=uuid.uuid4())
        with (
            patch.object(
                self.client.session,
                "send",
                return_value=gitlab_response(HTTPStatus.SERVICE_UNAVAILABLE),
            ),
            pytest.raises(gitlab.exceptions.GitlabGetError),
        ):
            _ = second_project.commit_history

    def test_branch_read_retries_and_404_is_empty(self) -> None:
        with patch.object(
            self.client.session,
            "send",
            side_effect=[
                gitlab_response(HTTPStatus.OK, project_payload(self.project)),
                gitlab_response(HTTPStatus.SERVICE_UNAVAILABLE),
                gitlab_response(
                    HTTPStatus.OK,
                    {
                        "name": settings.DJANGO_GIT_BRANCH_NAME,
                        "commit": {"id": USER_COMMIT_SHA},
                    },
                ),
            ],
        ) as send:
            assert GitlabManager.get_last_commit_hash(self.project) == USER_COMMIT_SHA
        assert send.call_count == 3  # noqa: PLR2004

        second_project = Project(id=uuid.uuid4())
        with patch.object(
            self.client.session,
            "send",
            side_effect=[
                gitlab_response(HTTPStatus.OK, project_payload(second_project)),
                gitlab_response(HTTPStatus.NOT_FOUND),
            ],
        ):
            assert GitlabManager.get_last_commit_hash(second_project) is None

        replacement_numeric_id = PROJECT_NUMERIC_ID + 1
        with patch.object(
            self.client.session,
            "send",
            side_effect=[
                gitlab_response(
                    HTTPStatus.OK,
                    project_payload(second_project, replacement_numeric_id),
                ),
                gitlab_response(
                    HTTPStatus.OK,
                    {
                        "name": settings.DJANGO_GIT_BRANCH_NAME,
                        "commit": {"id": USER_COMMIT_SHA},
                    },
                ),
            ],
        ) as send:
            assert GitlabManager.get_last_commit_hash(second_project) == USER_COMMIT_SHA
        assert (
            f"/projects/{replacement_numeric_id}/repository/branches/"
            in send.call_args_list[-1].args[0].url
        )

    def test_branch_read_exhaustion_propagates(self) -> None:
        with (
            patch.object(
                self.client.session,
                "send",
                side_effect=[
                    gitlab_response(HTTPStatus.OK, project_payload(self.project)),
                    *[
                        gitlab_response(HTTPStatus.SERVICE_UNAVAILABLE)
                        for _ in range(settings.DJANGO_GIT_RETRY_ATTEMPTS)
                    ],
                ],
            ) as send,
            pytest.raises(gitlab.exceptions.GitlabGetError),
        ):
            GitlabManager.get_last_commit_hash(self.project)

        assert send.call_count == settings.DJANGO_GIT_RETRY_ATTEMPTS + 1
