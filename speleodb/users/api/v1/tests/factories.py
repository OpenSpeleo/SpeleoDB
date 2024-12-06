import random

import factory
from django_countries import countries
from factory import Faker
from factory.django import DjangoModelFactory

from speleodb.users.models import SurveyTeam


class SurveyTeamFactory(DjangoModelFactory):
    name = Faker("name")
    description = factory.LazyAttribute(
        lambda obj: f"Team description for `{obj.name}`"
    )
    country = random.choice(countries)[0]

    class Meta:
        model = SurveyTeam
