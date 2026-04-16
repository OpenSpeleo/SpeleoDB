# -*- coding: utf-8 -*-

from __future__ import annotations

import pathlib
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

import django.test
import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.utils import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.common.enums import PermissionLevel
from speleodb.git_engine.gitlab_manager import GitlabError
from speleodb.middleware import DRFWrapResponseMiddleware
from speleodb.surveys.models import FileFormat
from speleodb.utils.exceptions import FileRejectedError

BASE_DIR = pathlib.Path(__file__).parent / "artifacts"


@pytest.mark.skip_if_lighttest
class UploadErrorHandlingTests(BaseAPIProjectTestCase):
    """Tests that upload failures are properly logged, reported to Sentry,
    and roll back the DB transaction."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )
        self.project.acquire_mutex(self.user)

    def _do_upload(self, **extra_data: Any) -> Any:
        test_file = BASE_DIR / "test_simple.tml"
        assert test_file.exists()
        with test_file.open(mode="rb") as f:
            data: dict[str, Any] = {
                "artifact": f,
                "message": "test commit",
                **extra_data,
            }
            return self.client.put(
                reverse(
                    "api:v2:project-upload",
                    kwargs={
                        "id": self.project.id,
                        "fileformat": FileFormat.ARIANE_TML.label.lower(),
                    },
                ),
                data,
                format="multipart",
                headers={"authorization": f"{self.header_prefix}{self.token.key}"},
            )

    @patch(
        "speleodb.api.v2.views.file.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_git_checkout_failure_logs_and_captures_sentry(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """A GitCommandError during checkout should produce a 500 response,
        log the traceback, and report to Sentry."""
        with patch.object(
            type(self.project),
            "checkout_commit_or_default_pull_branch",
            side_effect=RuntimeError("simulated git failure"),
        ):
            response = self._do_upload()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_sentry.assert_called_once()
        captured_exc = mock_sentry.call_args[0][0]
        assert isinstance(captured_exc, RuntimeError)
        assert "simulated git failure" in str(captured_exc)

    @patch(
        "speleodb.api.v2.views.file.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_git_failure_marks_transaction_for_rollback(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """When the upload pipeline fails with a 5xx,
        transaction.set_rollback(True) should mark the transaction
        for rollback so ATOMIC_REQUESTS does not commit partial writes."""
        with patch.object(
            type(self.project),
            "commit_and_push_project",
            side_effect=RuntimeError("simulated commit failure"),
        ):
            response = self._do_upload()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        # The transaction should be marked for rollback -- Django's
        # ATOMIC_REQUESTS will roll back instead of committing.
        assert connection.needs_rollback

    @patch(
        "speleodb.api.v2.views.file.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_gitlab_error_reports_to_sentry(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """A GitlabError should produce a 500 and be captured by Sentry."""
        with patch.object(
            type(self.project),
            "checkout_commit_or_default_pull_branch",
            side_effect=GitlabError("simulated gitlab outage"),
        ):
            response = self._do_upload()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_sentry.assert_called_once()

    @patch(
        "speleodb.api.v2.views.file.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_file_rejected_error_returns_415_without_sentry(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """A FileRejectedError should produce a 415 but NOT report to
        Sentry -- it is a user-input error, not an internal failure."""
        with patch.object(
            type(self.project),
            "checkout_commit_or_default_pull_branch",
            side_effect=FileRejectedError("bad file type"),
        ):
            response = self._do_upload()

        assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        mock_sentry.assert_not_called()

    @patch(
        "speleodb.api.v2.views.file.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_validation_error_returns_400_without_sentry(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """A ValidationError should produce a 400 but NOT report to
        Sentry -- it is a user-input error, not an internal failure."""
        with patch.object(
            type(self.project),
            "checkout_commit_or_default_pull_branch",
            side_effect=ValidationError("invalid data"),
        ):
            response = self._do_upload()

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        mock_sentry.assert_not_called()


@pytest.mark.skip_if_lighttest
class ConstructGitHistorySavepointTests(BaseAPIProjectTestCase):
    """Tests that IntegrityError inside construct_git_history_from_project
    does not corrupt the outer transaction."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )

    def test_integrity_error_does_not_break_transaction(self) -> None:
        """Suppressed IntegrityError in construct_git_history_from_project
        should use a savepoint so the outer transaction stays healthy."""
        mock_repo = MagicMock()

        mock_commit = MagicMock()
        mock_commit.hexsha = "a" * 40
        mock_commit.committed_date = 0
        mock_commit.authored_date = 0
        mock_commit.author.name = "Test"
        mock_commit.author.email = "test@test.com"
        mock_commit.message = "test"
        mock_commit.parents = []

        mock_repo.iter_commits.return_value = [mock_commit]

        with patch(
            "speleodb.surveys.models.project_commit.ProjectCommit.objects"
        ) as mock_manager:
            mock_manager.filter.return_value = []
            mock_manager.get_or_create.side_effect = IntegrityError(
                "duplicate key value"
            )

            self.project.construct_git_history_from_project(git_repo=mock_repo)

        assert not connection.needs_rollback


class MiddlewareExceptionReportingTests(django.test.TestCase):
    """DRFWrapResponseMiddleware is scoped to ``/api/v1/`` only. These tests
    pin the remaining v1 behaviour: an exception raised inside ``get_response``
    is captured by Sentry and turned into a 500 JSON response. They also pin
    that v2 paths bypass the middleware entirely (no Sentry capture, no
    envelope rewrap)."""

    @patch("speleodb.middleware.sentry_sdk.capture_exception", autospec=True)
    def test_v1_middleware_captures_unhandled_exception(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """An exception raised inside ``get_response`` for a ``/api/v1/``
        path must be captured by Sentry and returned as a 500 JSON
        response with the wrapped v1 envelope."""
        boom = RuntimeError("middleware test explosion")
        middleware = DRFWrapResponseMiddleware(
            get_response=MagicMock(side_effect=boom),
        )

        mock_request = MagicMock()
        projects_url = reverse("api:v1:projects")
        mock_request.path = projects_url
        mock_request.build_absolute_uri.return_value = (
            f"http://testserver{projects_url}"
        )

        response = middleware(mock_request)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_sentry.assert_called_once_with(boom)
        # Narrow to DRF Response so mypy sees `data`; at runtime the wrap
        # middleware always returns a SortedResponse (DRF subclass) for
        # /api/v1/ paths -- if that ever changes, this assertion tells us.
        assert isinstance(response, Response)
        assert response.data["success"] is False
        assert "error" in response.data
        assert response.data["url"].endswith(projects_url)

    @patch("speleodb.middleware.sentry_sdk.capture_exception", autospec=True)
    def test_v2_path_bypasses_middleware_sentry_capture(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """An exception raised inside ``get_response`` for a ``/api/v2/``
        path must NOT be captured by the wrap middleware -- v2 views are
        responsible for their own Sentry hooks via ``handle_exception``."""
        boom = RuntimeError("v2 must not be captured by wrap middleware")
        inner_get_response = MagicMock(side_effect=boom)
        middleware = DRFWrapResponseMiddleware(get_response=inner_get_response)

        mock_request = MagicMock()
        projects_url = reverse("api:v2:projects")
        mock_request.path = projects_url

        with pytest.raises(RuntimeError):
            middleware(mock_request)

        mock_sentry.assert_not_called()
        inner_get_response.assert_called_once_with(mock_request)
