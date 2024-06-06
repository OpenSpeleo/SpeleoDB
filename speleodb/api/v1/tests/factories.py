import random

import factory
from django_countries import countries
from factory import Faker
from factory import post_generation
from factory.django import DjangoModelFactory
from rest_framework.authtoken.models import Token

from speleodb.surveys.models import Permission
from speleodb.surveys.models import Project
from speleodb.users.models import User


class UserFactory(DjangoModelFactory):
    email = Faker("email")
    name = Faker("name")
    country = random.choice(countries)[0]

    class Meta:
        model = User

    @post_generation
    def password(self, *args, **kwargs):
        self.set_password(UserFactory.DEFAULT_PASSWORD)

    @classmethod
    def _after_postgeneration(cls, instance, create, results=None):
        """Save again the instance if creating and at least one hook ran."""
        if create and results and not cls._meta.skip_postgeneration_save:
            # Some post-generation hooks ran, and may have modified us.
            instance.save()

    @classmethod
    @property
    # Deprecation fix: https://github.com/linkml/linkml/pull/1959/files
    def DEFAULT_PASSWORD(cls):  # noqa: N802
        return "password"


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

    software = random.choice(Project.Software.choices)[0]

    class Meta:
        model = Project


class PermissionFactory(DjangoModelFactory):
    level = random.choice(Permission.Level.choices)[0]
    user = factory.SubFactory(UserFactory)
    project = factory.SubFactory(ProjectFactory)

    class Meta:
        model = Permission
