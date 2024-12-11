import random

from django.urls import reverse
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPITestCase
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import SurveyTeamFactory
from speleodb.api.v1.tests.factories import TeamPermissionFactory
from speleodb.api.v1.tests.factories import UserPermissionFactory
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.users.models import SurveyTeamMembership


class TestProjectInteraction(BaseAPITestCase):
    PROJECT_COUNT = 10

    def test_get_user_projects(self):
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        for project_id in range(self.PROJECT_COUNT):
            # spread equally some projects with user and team access
            project = ProjectFactory()
            if project_id % 2 == 0:
                _ = UserPermissionFactory(
                    target=self.user,
                    level=random.choice(UserPermission.Level.values),
                    project=project,
                )
            else:
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
                    level=random.choice(TeamPermission.Level.values),
                    project=project,
                )

        endpoint = reverse("api:v1:list_all_projects")

        auth = self.header_prefix + self.token.key
        response = self.client.get(endpoint, headers={"authorization": auth})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == self.PROJECT_COUNT

        attributes = [
            "creation_date",
            "description",
            "fork_from",
            "id",
            "latitude",
            "longitude",
            "modified_date",
            "active_mutex",
            "name",
            "user_permission",
        ]

        for project in response.data["data"]:
            assert all(attr in project for attr in attributes)

        target = {
            "success": True,
            "url": f"http://testserver{endpoint}",
        }

        for key, val in target.items():
            assert val == response.data[key]
