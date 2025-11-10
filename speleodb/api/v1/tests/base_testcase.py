# -*- coding: utf-8 -*-

from __future__ import annotations

import random
from enum import Enum
from typing import TYPE_CHECKING

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import SurveyTeamFactory
from speleodb.api.v1.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v1.tests.factories import TeamPermissionFactory
from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.api.v1.tests.factories import UserPermissionFactory
from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import Project
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembershipRole
from speleodb.users.models import User
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from rest_framework.authtoken.models import Token


class PermissionType(Enum):
    USER = "user"
    TEAM = "team"


class BaseUserTestCaseMixin(TestCase):
    user: User
    token: Token

    def setUp(self) -> None:
        super().setUp()
        self.user = UserFactory.create()
        self.token = TokenFactory.create(user=self.user)

        # Clear caches to avoid carrying over values from one test to the other.
        self.user.void_permission_cache()


class BaseAPITestCase(BaseUserTestCaseMixin):
    """API-enabled TestCase Token authentication"""

    client: APIClient
    header_prefix = "Token "
    auth: str

    def setUp(self) -> None:
        super().setUp()
        self.client = APIClient(enforce_csrf_checks=False)
        self.auth = self.header_prefix + self.token.key


class BaseProjectTestCaseMixin(BaseUserTestCaseMixin):
    project: Project

    def setUp(self) -> None:
        super().setUp()
        self.project = ProjectFactory.create(created_by=self.user.email)

    def set_test_project_permission(
        self, level: PermissionLevel, permission_type: PermissionType
    ) -> None:
        if level == PermissionLevel.ADMIN and permission_type == PermissionType.TEAM:
            pytest.skip("Combination not allowed")

        match permission_type:
            case PermissionType.USER:
                # Update or create permission to avoid duplicates
                # UserPermission.objects.update_or_create(
                #     target=self.user, project=self.project, defaults={"level": level}
                # )
                _ = UserPermissionFactory(
                    target=self.user, level=level, project=self.project
                )

            case PermissionType.TEAM:
                if level not in PermissionLevel.values_no_admin:
                    raise ValueError(f"Invalid permission level for team: {level}")

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

            case _:
                raise TypeError(f"Received unexpected level type: `{type(level)}`")


class BaseAPIProjectTestCase(BaseProjectTestCaseMixin, BaseAPITestCase):
    pass
