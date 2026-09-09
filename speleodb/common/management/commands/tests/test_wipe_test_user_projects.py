# -*- coding: utf-8 -*-

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import gitlab.exceptions
import pytest
from django.core.management import call_command
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout

from speleodb.api.v2.tests.base_testcase import BaseProjectTestCaseMixin
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.common.enums import PermissionLevel
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.surveys.models import Project


class TestWipeTestUserProjects(BaseProjectTestCaseMixin):
    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(PermissionLevel.ADMIN, PermissionType.USER)
        self.client: MagicMock = MagicMock()
        self.enterContext(patch.object(GitlabManager, "_gl", self.client))
        self.enterContext(patch.object(GitlabManager, "_initialize"))
        self.enterContext(
            patch(
                "speleodb.common.management.commands.wipe_test_user_projects.time.sleep"
            )
        )

    def _run_command(self) -> None:
        call_command(
            "wipe_test_user_projects",
            user_email=self.user.email,
            skip_user_confirmation=True,
        )

    def test_deletes_local_project_after_successful_remote_delete(self) -> None:
        self._run_command()

        self.client.projects.get.return_value.delete.assert_called_once_with()
        assert not Project.objects.filter(id=self.project.id).exists()

    def test_deletes_local_project_only_when_remote_is_confirmed_missing(self) -> None:
        self.client.projects.get.side_effect = gitlab.exceptions.GitlabGetError(
            "not found", response_code=404
        )

        self._run_command()

        assert not Project.objects.filter(id=self.project.id).exists()
        self.client.projects.get.return_value.delete.assert_not_called()

    def test_preserves_local_project_on_other_lookup_failures(self) -> None:
        for status in (400, 403, 429, 500, 502, 503, 504):
            with self.subTest(status=status):
                error: gitlab.exceptions.GitlabGetError = (
                    gitlab.exceptions.GitlabGetError("upstream failure", status)
                )
                self.client.projects.get.side_effect = error
                with pytest.raises(gitlab.exceptions.GitlabGetError) as raised:
                    self._run_command()
                assert raised.value is error
                assert Project.objects.filter(id=self.project.id).exists()
                self.client.projects.get.return_value.delete.assert_not_called()

    def test_preserves_local_project_on_authentication_or_transport_failure(
        self,
    ) -> None:
        errors: tuple[Exception, ...] = (
            gitlab.exceptions.GitlabAuthenticationError("invalid token", 401),
            Timeout("upstream timed out"),
            RequestsConnectionError("connection failed"),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__):
                self.client.projects.get.side_effect = error
                with pytest.raises(type(error)) as raised:
                    self._run_command()
                assert raised.value is error
                assert Project.objects.filter(id=self.project.id).exists()

    def test_preserves_local_project_when_remote_delete_fails(self) -> None:
        self.client.projects.get.return_value.delete.side_effect = (
            gitlab.exceptions.GitlabDeleteError("delete failed", 503)
        )
        with pytest.raises(gitlab.exceptions.GitlabDeleteError):
            self._run_command()

        assert Project.objects.filter(id=self.project.id).exists()
