import random

from django.test import TestCase
from rest_framework.test import APIClient

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import SurveyTeamFactory
from speleodb.api.v1.tests.factories import TeamPermissionFactory
from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.api.v1.tests.factories import UserFactory
from speleodb.api.v1.tests.factories import UserPermissionFactory
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.users.models import SurveyTeamMembership

AnyPermissionLevel = UserPermission.Level | TeamPermission.Level


class BaseAPITestCase(TestCase):
    """API-enabled TestCase Token authentication"""

    header_prefix = "Token "

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)

        self.user = UserFactory()
        self.token = TokenFactory(user=self.user)


class BaseAPIProjectTestCase(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory(created_by=self.user)

    def set_test_project_permission(self, level: AnyPermissionLevel):
        if isinstance(level, UserPermission.Level):
            _ = UserPermissionFactory(
                target=self.user, level=level, project=self.project
            )

        elif isinstance(level, TeamPermission.Level):
            # Create a team for the user - assign the user to the team
            team = SurveyTeamFactory()
            _ = SurveyTeamMembership.objects.create(
                user=self.user,
                team=team,
                role=random.choice(SurveyTeamMembership.Role.values),
            )

            # Give the newly created permission to the project
            _ = TeamPermissionFactory(
                target=team,
                level=level,
                project=self.project,
            )

        else:
            raise TypeError(f"Received unexpected level type: `{type(level)}`")
