# -*- coding: utf-8 -*-

from __future__ import annotations

import random
from itertools import cycle
from typing import TYPE_CHECKING

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.serializers.project import ProjectSerializer
from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import SurveyTeamFactory
from speleodb.api.v2.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v2.tests.factories import TeamProjectPermissionFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import SurveyTeamMembershipRole

if TYPE_CHECKING:
    from speleodb.surveys.models import TeamProjectPermission
    from speleodb.surveys.models import UserProjectPermission


class TestProjectInteraction(BaseAPITestCase):
    PROJECT_COUNT = 25

    def test_get_user_projects(self) -> None:
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        perm_level_iter = cycle(PermissionLevel.values_no_admin)

        perm_lvls: list[UserProjectPermission | TeamProjectPermission] = []

        for project_id in range(self.PROJECT_COUNT):
            # spread equally some projects with user and team access
            project = ProjectFactory.create(created_by=self.user.email)
            if project_id % 2 == 0:
                perm_lvls.append(
                    UserProjectPermissionFactory(  # type: ignore[arg-type]
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
                    TeamProjectPermissionFactory(  # type: ignore[arg-type]
                        target=team,
                        level=perm_level,
                        project=project,
                    )
                )

        endpoint = reverse("api:v2:projects")

        auth = self.header_prefix + self.token.key
        response = self.client.get(endpoint, headers={"authorization": auth})

        assert response.status_code == status.HTTP_200_OK, response.data
        assert len(response.data) == len(perm_lvls)

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
            "type",
        ]

        for project_data in response.data:
            assert all(attr in project_data for attr in attributes)


class TestProjectListPermissions(BaseAPITestCase):
    def test_permission_queries_do_not_grow_with_accessible_projects(self) -> None:
        team = SurveyTeamFactory.create()
        SurveyTeamMembershipFactory.create(user=self.user, team=team)
        expected: dict[str, str] = {}
        query_counts: list[int] = []
        for index in range(3):
            project = ProjectFactory.create(created_by=self.user.email)
            if index == 0:
                UserProjectPermissionFactory.create(
                    target=self.user, project=project, level=PermissionLevel.READ_ONLY
                )
                expected[str(project.pk)] = PermissionLevel.READ_ONLY.label
            else:
                TeamProjectPermissionFactory.create(
                    target=team, project=project, level=PermissionLevel.READ_AND_WRITE
                )
                expected[str(project.pk)] = PermissionLevel.READ_AND_WRITE.label
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(
                    reverse("api:v2:projects"),
                    headers={"authorization": self.auth},
                )
            assert response.status_code == status.HTTP_200_OK
            assert {row["id"]: row["permission"] for row in response.data} == expected
            query_counts.append(len(queries))
        assert query_counts[0] > 0
        assert query_counts[1:] == [query_counts[0]] * 2

    def test_effective_permissions_refresh_after_grant_and_membership_revocation(
        self,
    ) -> None:
        project = ProjectFactory.create(created_by=self.user.email)
        team = SurveyTeamFactory.create()
        membership = SurveyTeamMembershipFactory.create(user=self.user, team=team)
        direct = UserProjectPermissionFactory.create(
            target=self.user, project=project, level=PermissionLevel.READ_ONLY
        )
        team_grant = TeamProjectPermissionFactory.create(
            target=team, project=project, level=PermissionLevel.READ_AND_WRITE
        )
        inaccessible = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user, project=inaccessible, is_active=False
        )
        ProjectFactory.create(created_by=self.user.email)

        for expected_level in (
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.READ_ONLY,
            PermissionLevel.READ_ONLY,
        ):
            response = self.client.get(
                reverse("api:v2:projects"), headers={"authorization": self.auth}
            )
            assert response.status_code == status.HTTP_200_OK
            assert {row["id"]: row["permission"] for row in response.data} == {
                str(project.pk): expected_level.label
            }
            if membership.is_active:
                membership.is_active = False
                membership.save()
            else:
                membership.is_active = True
                membership.save()
                team_grant.is_active = False
                team_grant.save()

        direct.is_active = False
        direct.save()
        response = self.client.get(
            reverse("api:v2:projects"), headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_explicit_permission_mapping_does_not_fall_back_to_individual_lookup(
        self,
    ) -> None:
        project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user, project=project, level=PermissionLevel.ADMIN
        )
        serializer = ProjectSerializer(
            context={"user": self.user, "project_permissions": {}}
        )
        with CaptureQueriesContext(connection) as queries:
            permission = serializer.get_permission(project)
        assert permission is None
        assert len(queries) == 0
