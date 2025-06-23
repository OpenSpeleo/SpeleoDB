# -*- coding: utf-8 -*-

from __future__ import annotations

import random
from typing import TYPE_CHECKING
from typing import Any

import factory
from django.utils import timezone
from django_countries import countries
from factory import Faker
from factory import post_generation
from factory.django import DjangoModelFactory
from rest_framework.authtoken.models import Token

from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import Project
from speleodb.surveys.models import PublicAnnoucement
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.surveys.models.platform_base import SurveyPlatformEnum
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.users.models import User

if TYPE_CHECKING:
    from factory.base import StubObject


class UserFactory(DjangoModelFactory[User]):
    email: str = Faker("email")  # type: ignore[assignment]
    name: str = Faker("name")  # type: ignore[assignment]
    country: str = random.choice(countries).code  # pyright: ignore[reportAttributeAccessIssue]

    class Meta:
        model = User

    @post_generation
    def password(self, *args: Any, **kwargs: Any) -> None:
        self.set_password(UserFactory.DEFAULT_PASSWORD())  # type: ignore[attr-defined]

    @classmethod
    def _after_postgeneration(
        cls,
        instance: User | StubObject,
        create: bool,
        results: dict[str, Any] | None = None,
    ) -> None:
        """Save again the instance if creating and at least one hook ran."""
        if create and results and not cls._meta.skip_postgeneration_save:  # type: ignore[attr-defined]
            # Some post-generation hooks ran, and may have modified us.
            instance.save()  # type: ignore[union-attr]

    @classmethod
    def DEFAULT_PASSWORD(cls) -> str:  # noqa: N802
        return "password"


class SurveyTeamFactory(DjangoModelFactory[SurveyTeam]):
    name: str = Faker("name")  # type: ignore[assignment]
    description: str = factory.LazyAttribute(
        lambda obj: f"Team description for `{obj.name}`"
    )  # type: ignore[assignment]
    country = random.choice(countries)[0]

    class Meta:
        model = SurveyTeam


class SurveyTeamMembershipFactory(DjangoModelFactory[SurveyTeamMembership]):
    user: User = factory.SubFactory(UserFactory)  # type: ignore[assignment]
    team: SurveyTeam = factory.SubFactory(SurveyTeamFactory)  # type: ignore[assignment]
    role = random.choice(SurveyTeamMembership.Role.values)

    class Meta:
        model = SurveyTeamMembership


class TokenFactory(DjangoModelFactory[Token]):
    key: str = Faker("password", length=40, special_chars=True, upper_case=True)  # type: ignore[assignment]
    user: User = factory.SubFactory(UserFactory)  # type: ignore[assignment]

    class Meta:
        model = Token


class ProjectFactory(DjangoModelFactory[Project]):
    name = factory.Sequence(lambda n: f"Test Cave {n:04d}")
    description: str = factory.LazyAttribute(
        lambda obj: f"Project description for `{obj.name}`"
    )  # type: ignore[assignment]
    longitude: float = Faker("longitude")  # type: ignore[assignment]
    latitude: float = Faker("latitude")  # type: ignore[assignment]

    country = random.choice(countries).code  # pyright: ignore[reportAttributeAccessIssue]

    created_by: User = factory.SubFactory(UserFactory)  # type: ignore[assignment]

    class Meta:
        model = Project


class UserPermissionFactory(DjangoModelFactory[UserPermission]):
    level = random.choice(PermissionLevel.values)
    target: User = factory.SubFactory(UserFactory)  # type: ignore[assignment]
    project: Project = factory.SubFactory(ProjectFactory)  # type: ignore[assignment]

    class Meta:
        model = UserPermission


class TeamPermissionFactory(DjangoModelFactory[TeamPermission]):
    level = random.choice(PermissionLevel.values)
    target: SurveyTeam = factory.SubFactory(SurveyTeamFactory)  # type: ignore[assignment]
    project: Project = factory.SubFactory(ProjectFactory)  # type: ignore[assignment]

    class Meta:
        model = TeamPermission


class PublicAnnoucementFactory(DjangoModelFactory[PublicAnnoucement]):
    """
    Factory for creating PublicAnnoucement instances for testing.
    """

    class Meta:
        model = PublicAnnoucement

    # ---------- Default Values for Required Fields ----------

    title = factory.Sequence(lambda n: f"Announcement {n}")
    header: str = Faker("sentence")  # type: ignore[assignment]
    message: str = Faker("paragraph")  # type: ignore[assignment]

    software = SurveyPlatformEnum.WEB
    version = "1.0.0"
    is_active = True

    # Timestamps — allow override in tests if necessary
    creation_date: Any = factory.LazyFunction(timezone.now)
    modified_date: Any = factory.LazyFunction(timezone.now)
    expiracy_date: Any = None  # Default: no expiration
