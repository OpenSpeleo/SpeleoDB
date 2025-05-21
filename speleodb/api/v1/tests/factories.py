import random

import factory
from django_countries import countries
from factory import Faker
from factory import post_generation
from factory.django import DjangoModelFactory
from rest_framework.authtoken.models import Token

from speleodb.surveys.models import Project
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.users.models import User


class UserFactory(DjangoModelFactory):
    email: str = Faker("email")
    name: str = Faker("name")
    country: str = random.choice(countries)[0]

    class Meta:
        model = User

    @post_generation
    def password(self, *args, **kwargs) -> None:
        self.set_password(UserFactory.DEFAULT_PASSWORD())

    @classmethod
    def _after_postgeneration(cls, instance, create, results=None):
        """Save again the instance if creating and at least one hook ran."""
        if create and results and not cls._meta.skip_postgeneration_save:
            # Some post-generation hooks ran, and may have modified us.
            instance.save()

    @classmethod
    def DEFAULT_PASSWORD(cls):  # noqa: N802
        return "password"


class SurveyTeamFactory(DjangoModelFactory):
    name = Faker("name")
    description = factory.LazyAttribute(
        lambda obj: f"Team description for `{obj.name}`"
    )
    country = random.choice(countries)[0]

    class Meta:
        model = SurveyTeam


class SurveyTeamMembershipFactory(DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    team = factory.SubFactory(SurveyTeamFactory)
    role = random.choice(SurveyTeamMembership.Role.values)

    class Meta:
        model = SurveyTeamMembership


class TokenFactory(DjangoModelFactory):
    key = Faker("password", length=40, special_chars=True, upper_case=True)
    user = factory.SubFactory(UserFactory)

    class Meta:
        model = Token


class ProjectFactory(DjangoModelFactory):
    name = factory.Sequence(lambda n: f"Test Cave {n:04d}")
    description = factory.LazyAttribute(
        lambda obj: f"Project description for `{obj.name}`"
    )
    longitude = Faker("longitude")
    latitude = Faker("latitude")

    country = random.choice(countries)[0]

    created_by = factory.SubFactory(UserFactory)

    class Meta:
        model = Project


class UserPermissionFactory(DjangoModelFactory):
    level = random.choice(UserPermission.Level.values)
    target = factory.SubFactory(UserFactory)
    project = factory.SubFactory(ProjectFactory)

    class Meta:
        model = UserPermission


class TeamPermissionFactory(DjangoModelFactory):
    level = random.choice(TeamPermission.Level.values)
    target = factory.SubFactory(SurveyTeamFactory)
    project = factory.SubFactory(ProjectFactory)

    class Meta:
        model = TeamPermission
