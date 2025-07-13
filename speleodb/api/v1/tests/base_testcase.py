# -*- coding: utf-8 -*-

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from django.test import TestCase
from rest_framework.test import APIClient

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import SurveyTeamFactory
from speleodb.api.v1.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v1.tests.factories import TeamPermissionFactory
from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import Project
from speleodb.surveys.models import UserPermission
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembershipRole
from speleodb.users.models import User
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from rest_framework.authtoken.models import Token


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
            # Update or create permission to avoid duplicates
            UserPermission.objects.update_or_create(
                target=self.user, project=self.project, defaults={"level": level}
            )

        elif isinstance(level, PermissionLevel):
            # Create a team for the user - assign the user to the team
            team: SurveyTeam = SurveyTeamFactory.create()

            _ = SurveyTeamMembershipFactory.create(
                user=self.user,
                team=team,
                role=random.choice(SurveyTeamMembershipRole.values),
            )

            # Give the newly created permission to the project
            _ = TeamPermissionFactory.create(
                target=team,
                level=level,
                project=self.project,
            )

        else:
            raise TypeError(f"Received unexpected level type: `{type(level)}`")
