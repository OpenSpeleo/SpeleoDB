# -*- coding: utf-8 -*-

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from speleodb.api.v2.tests.factories import SurveyTeamFactory
from speleodb.api.v2.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v2.tests.factories import TeamProjectPermissionFactory
from speleodb.api.v2.tests.factories import TokenFactory
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import SurveyTeamMembershipRole
from speleodb.surveys.models import UserProjectPermission
from speleodb.testing.gitlab_pool import canonical_project
from speleodb.testing.gitlab_pool import canonical_user

if TYPE_CHECKING:
    from rest_framework.authtoken.models import Token

    from speleodb.surveys.models import Project
    from speleodb.users.models import SurveyTeam
    from speleodb.users.models import User


class PermissionType(Enum):
    USER = "user"
    TEAM = "team"


class BaseUserTestCaseMixin(TestCase):
    user: User
    token: Token

    def setUp(self) -> None:
        super().setUp()
        self.user = canonical_user("A")
        self.token = TokenFactory.create(user=self.user)


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
        level: PermissionLevel = PermissionLevel(
            getattr(self, "level", PermissionLevel.ADMIN)
        )
        self.project = canonical_project(level)

    def set_test_project_permission(
        self, level: PermissionLevel, permission_type: PermissionType
    ) -> None:
        if level == PermissionLevel.ADMIN and permission_type == PermissionType.TEAM:
            pytest.skip("Combination not allowed")

        match permission_type:
            case PermissionType.USER:
                UserProjectPermission.objects.update_or_create(
                    target=self.user,
                    project=self.project,
                    defaults={"level": level, "is_active": True},
                )

            case PermissionType.TEAM:
                if level not in PermissionLevel.values_no_admin:
                    raise ValueError(f"Invalid permission level for team: {level}")

                # Create a team for the user - assign the user to the team
                team: SurveyTeam = SurveyTeamFactory.create()

                _ = SurveyTeamMembershipFactory.create(
                    user=self.user,
                    team=team,
                    role=SurveyTeamMembershipRole.MEMBER,
                )

                # Give the newly created permission to the project
                _ = TeamProjectPermissionFactory.create(
                    target=team,
                    level=level,
                    project=self.project,
                )

            case _:
                raise TypeError(f"Received unexpected level type: `{type(level)}`")


class BaseAPIProjectTestCase(BaseProjectTestCaseMixin, BaseAPITestCase):
    pass
