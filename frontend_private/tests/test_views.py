from __future__ import annotations

import hashlib
import random
from typing import Any

from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse
from parameterized.parameterized import parameterized
from parameterized.parameterized import parameterized_class
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseProjectTestCaseMixin
from speleodb.api.v1.tests.base_testcase import BaseUserTestCaseMixin
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.api.v1.tests.factories import SurveyTeamFactory
from speleodb.api.v1.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v1.tests.factories import UserPermissionFactory
from speleodb.surveys.models import PermissionLevel
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembershipRole
from speleodb.users.tests.factories import UserFactory


class BaseTestCase(BaseUserTestCaseMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()

    def execute_test(
        self,
        view_name: str,
        kwargs: Any | None = None,
        expected_status: int = status.HTTP_200_OK,
    ) -> None:
        url = reverse(f"private:{view_name}", kwargs=kwargs)

        self.client.force_login(self.user)
        response = self.client.get(url)

        if expected_status != status.HTTP_302_FOUND:
            assert isinstance(response, HttpResponse), type(response)
        else:
            assert isinstance(response, HttpResponseRedirect), type(response)

        assert response.status_code == expected_status

        assert response["Content-Type"].startswith("text/html"), response[
            "Content-Type"
        ]


class UserViewsTest(BaseTestCase):
    @parameterized.expand(
        [
            "user_dashboard",
            "user_authtoken",
            "user_feedback",
            "user_password",
            "user_preferences",
        ]
    )
    def test_view_with_no_args(self, view_name: str) -> None:
        self.execute_test(view_name)


@parameterized_class(
    ("role"), [(SurveyTeamMembershipRole.LEADER,), (SurveyTeamMembershipRole.MEMBER,)]
)
class TeamViewsTest(BaseTestCase):
    role: SurveyTeamMembershipRole

    def setUp(self) -> None:
        super().setUp()

        self.team: SurveyTeam = SurveyTeamFactory.create()

        # Must make the user is at least a member of the team - one of each
        _ = SurveyTeamMembershipFactory(team=self.team, user=self.user, role=self.role)

    @parameterized.expand(["teams", "team_new"])
    def test_view_with_no_args(self, view_name: str) -> None:
        self.execute_test(view_name)

    @parameterized.expand(["team_details", "team_memberships", "team_danger_zone"])
    def test_view_with_team_id(self, view_name: str) -> None:
        expected_status = (
            status.HTTP_200_OK
            if self.role == SurveyTeamMembershipRole.LEADER
            or view_name != "team_danger_zone"
            else status.HTTP_302_FOUND
        )
        self.execute_test(
            view_name, {"team_id": self.team.id}, expected_status=expected_status
        )


@parameterized_class(
    ("level", "permission_type"),
    [
        (PermissionLevel.READ_ONLY, PermissionType.USER),
        (PermissionLevel.READ_ONLY, PermissionType.TEAM),
        (PermissionLevel.READ_AND_WRITE, PermissionType.USER),
        (PermissionLevel.READ_AND_WRITE, PermissionType.TEAM),
        (PermissionLevel.ADMIN, PermissionType.USER),
    ],
)
class ProjectViewsTest(BaseProjectTestCaseMixin, BaseTestCase):
    level: PermissionLevel
    permission_type: PermissionType

    def setUp(self) -> None:
        super().setUp()

        self.set_test_project_permission(
            level=self.level,
            permission_type=self.permission_type,
        )

    @parameterized.expand(["projects", "project_new"])
    def test_view_with_no_args(self, view_name: str) -> None:
        self.execute_test(view_name)

    @parameterized.expand(
        [
            "project_details",
            "project_user_permissions",
            "project_team_permissions",
            "project_mutexes",
            "project_revisions",
            "project_git_instructions",
            "project_danger_zone",
        ]
    )
    def test_view_with_project_id(self, view_name: str) -> None:
        expected_status = (
            status.HTTP_200_OK
            if self.level == PermissionLevel.ADMIN or view_name != "project_danger_zone"
            else status.HTTP_302_FOUND
        )

        self.execute_test(
            view_name, {"project_id": self.project.id}, expected_status=expected_status
        )

    @parameterized.expand([True, False, None])
    def test_view_with_project_id_and_maybe_lock(
        self, project_is_locked: bool | None
    ) -> None:
        """`project_is_locked` can take 3 values:
        - True: Yes the project is locked by the user
        - False: No the project is not locked by the user and by no-one else.
        - None: The project is locked by a different user.
        """

        expected_status: int
        match project_is_locked:
            case True:
                if self.level in [
                    PermissionLevel.READ_ONLY,
                    PermissionLevel.READ_ONLY,
                ]:
                    return  # this user can not acquire the lock
                self.project.acquire_mutex(self.user)
                expected_status = status.HTTP_200_OK
            case False:
                expected_status = status.HTTP_302_FOUND
            case None:
                # somebody has acquired the lock
                user = UserFactory.create()
                _ = UserPermissionFactory(
                    target=user,
                    level=PermissionLevel.READ_AND_WRITE,
                    project=self.project,
                )
                self.project.acquire_mutex(user)
                expected_status = status.HTTP_302_FOUND
            case _:
                raise ValueError(
                    f"Unexpected value for `project_is_locked`: {project_is_locked}"
                )

        self.execute_test(
            "project_upload",
            {"project_id": self.project.id},
            expected_status=expected_status,
        )

    def test_view_with_project_id_and_gitsha(self) -> None:
        self.execute_test(
            "project_revision_explorer",
            {
                "project_id": self.project.id,
                "hexsha": hashlib.sha1(
                    str(random.random()).encode("utf-8"),
                    usedforsecurity=False,
                ).hexdigest(),
            },
        )
