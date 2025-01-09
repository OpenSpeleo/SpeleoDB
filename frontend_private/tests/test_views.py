import hashlib
import random

import pytest
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse
from parameterized import parameterized
from parameterized import parameterized_class
from rest_framework import status

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import SurveyTeamFactory
from speleodb.api.v1.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v1.tests.factories import TeamPermissionFactory
from speleodb.api.v1.tests.factories import UserFactory
from speleodb.api.v1.tests.factories import UserPermissionFactory
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership


class BaseTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory()

    def execute_test(
        self,
        view_name: str,
        kwargs: dict | None = None,
        expected_status: int = status.HTTP_200_OK,
    ):
        url = reverse(f"private:{view_name}", kwargs=kwargs)
        self.client.login(
            email=self.user.email, password=UserFactory.DEFAULT_PASSWORD()
        )
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
    def test_view_with_no_args(self, view_name: str):
        self.execute_test(view_name)


@parameterized_class(
    ("role"), [(SurveyTeamMembership.Role.LEADER,), (SurveyTeamMembership.Role.MEMBER,)]
)
class TeamViewsTest(BaseTestCase):
    def setUp(self):
        super().setUp()

        self.team: SurveyTeam = SurveyTeamFactory()

        # Must make the user is at least a member of the team - one of each
        _ = SurveyTeamMembershipFactory(team=self.team, user=self.user, role=self.role)

    @parameterized.expand(["teams", "team_new"])
    def test_view_with_no_args(self, view_name: str):
        self.execute_test(view_name)

    @parameterized.expand(["team_details", "team_memberships", "team_danger_zone"])
    def test_view_with_team_id(self, view_name: str):
        expected_status = (
            status.HTTP_200_OK
            if self.role == SurveyTeamMembership.Role.LEADER
            or view_name != "team_danger_zone"
            else status.HTTP_302_FOUND
        )
        self.execute_test(
            view_name, {"team_id": self.team.id}, expected_status=expected_status
        )


@parameterized_class(
    ("level"),
    [
        (TeamPermission.Level.READ_AND_WRITE,),
        (TeamPermission.Level.READ_ONLY,),
        (UserPermission.Level.ADMIN,),
        (UserPermission.Level.READ_AND_WRITE,),
        (UserPermission.Level.READ_ONLY,),
    ],
)
class ProjectViewsTest(BaseTestCase):
    def setUp(self):
        super().setUp()

        self.project = ProjectFactory(created_by=self.user)

        if isinstance(self.level, TeamPermission.Level):
            team: SurveyTeam = SurveyTeamFactory()

            # Must make the user is at least a member of the team - random role
            _ = SurveyTeamMembershipFactory(team=team, user=self.user)

            _ = TeamPermissionFactory(
                target=team, level=self.level, project=self.project
            )
        elif isinstance(self.level, UserPermission.Level):
            _ = UserPermissionFactory(
                target=self.user, level=self.level, project=self.project
            )
        else:
            raise TypeError(f"Unknown type received for level: {type(self.level)}")

    @parameterized.expand(["projects", "project_new"])
    def test_view_with_no_args(self, view_name: str):
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
    def test_view_with_project_id(self, view_name: str):
        expected_status = (
            status.HTTP_200_OK
            if self.level == UserPermission.Level.ADMIN
            or view_name != "project_danger_zone"
            else status.HTTP_302_FOUND
        )

        self.execute_test(
            view_name, {"project_id": self.project.id}, expected_status=expected_status
        )

    @parameterized.expand([True, False, None])
    def test_view_with_project_id_and_maybe_lock(self, project_is_locked: bool | None):
        """`project_is_locked` can take 3 values:
        - True: Yes the project is locked by the user
        - False: No the project is not locked by the user and by no-one else.
        - None: The project is locked by a different user.
        """

        match project_is_locked:
            case True:
                if self.level in [
                    UserPermission.Level.READ_ONLY,
                    TeamPermission.Level.READ_ONLY,
                ]:
                    pytest.skip("This user can not acquire the lock")
                self.project.acquire_mutex(self.user)
                expected_status = status.HTTP_200_OK
            case False:
                expected_status = status.HTTP_302_FOUND
            case None:
                # somebody has acquired the lock
                user = UserFactory()
                _ = UserPermissionFactory(
                    target=user,
                    level=UserPermission.Level.READ_AND_WRITE,
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

    def test_view_with_project_id_and_gitsha(self):
        self.execute_test(
            "project_revision_explorer",
            {
                "project_id": self.project.id,
                "hexsha": hashlib.sha1(  # noqa: S324
                    str(random.random()).encode("utf-8")
                ).hexdigest(),
            },
        )
