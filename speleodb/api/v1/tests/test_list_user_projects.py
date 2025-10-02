# -*- coding: utf-8 -*-

from __future__ import annotations

import random
from itertools import cycle

from django.urls import reverse
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPITestCase
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import SurveyTeamFactory
from speleodb.api.v1.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v1.tests.factories import TeamPermissionFactory
from speleodb.api.v1.tests.factories import UserPermissionFactory
from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.users.models import SurveyTeamMembershipRole


class TestProjectInteraction(BaseAPITestCase):
    PROJECT_COUNT = 25

    def test_get_user_projects(self) -> None:
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        perm_level_iter = cycle(PermissionLevel.values_no_admin)

        perm_lvls: list[UserPermission | TeamPermission] = []

        for project_id in range(self.PROJECT_COUNT):
            # spread equally some projects with user and team access
            project = ProjectFactory.create(created_by=self.user)
            if project_id % 2 == 0:
                perm_lvls.append(
                    UserPermissionFactory(  # type: ignore[arg-type]
                        target=self.user,
                        level=next(perm_level_iter),
                        project=project,
                    )
                )

            else:
                # Create a team for the user - assign the user to the team
                team = SurveyTeamFactory()
                _ = SurveyTeamMembershipFactory(
                    user=self.user,
                    team=team,
                    role=random.choice(SurveyTeamMembershipRole.values),
                )

                perm_level = next(perm_level_iter)
                if perm_level == PermissionLevel.ADMIN.value:
                    perm_level = next(perm_level_iter)

                # Give the newly created permission to the project
                perm_lvls.append(
                    TeamPermissionFactory(  # type: ignore[arg-type]
                        target=team,
                        level=perm_level,
                        project=project,
                    )
                )

        endpoint = reverse("api:v1:projects")

        auth = self.header_prefix + self.token.key
        response = self.client.get(endpoint, headers={"authorization": auth})

        assert response.status_code == status.HTTP_200_OK, response.data
        assert len(response.data["data"]) == len(
            [
                perm
                for perm in perm_lvls
                if perm.level > PermissionLevel.WEB_VIEWER.value
            ]
        )

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
            "permission",
        ]

        for project_data in response.data["data"]:
            assert all(attr in project_data for attr in attributes)

        target = {
            "success": True,
            "url": f"http://testserver{endpoint}",
        }

        for key, val in target.items():
            assert val == response.data[key]
