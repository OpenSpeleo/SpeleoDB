import random

from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import SurveyTeamFactory
from speleodb.api.v1.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v1.tests.factories import TeamPermissionFactory
from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.api.v1.tests.factories import UserFactory
from speleodb.api.v1.tests.factories import UserPermissionFactory
from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import Project
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.users.models import User


class BaseAPITestCase(TestCase):
    """API-enabled TestCase Token authentication"""

    client: APIClient
    header_prefix = "Token "
    user: User
    token: Token

    def setUp(self) -> None:
        self.client = APIClient(enforce_csrf_checks=False)

        self.user = UserFactory.create()
        self.token = TokenFactory.create(user=self.user)


class BaseAPIProjectTestCase(BaseAPITestCase):
    project: Project

    def setUp(self) -> None:
        super().setUp()
        self.project = ProjectFactory.create(created_by=self.user)

    def set_test_project_permission(self, level: PermissionLevel) -> None:
        if isinstance(level, PermissionLevel):
            _ = UserPermissionFactory.create(
                target=self.user, level=level, project=self.project
            )

        elif isinstance(level, PermissionLevel):
            # Create a team for the user - assign the user to the team
            team: SurveyTeam = SurveyTeamFactory.create()

            _ = SurveyTeamMembershipFactory.create(
                user=self.user,
                team=team,
                role=random.choice(SurveyTeamMembership.Role.values),
            )

            # Give the newly created permission to the project
            _ = TeamPermissionFactory.create(
                target=team,
                level=level,
                project=self.project,
            )

        else:
            raise TypeError(f"Received unexpected level type: `{type(level)}`")
