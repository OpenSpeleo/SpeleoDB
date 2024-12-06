#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pathlib

import pytest
from django.apps import apps
from dotenv import load_dotenv

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.surveys.models import Project
from speleodb.users.api.v1.tests.factories import SurveyTeamFactory
from speleodb.users.models import SurveyTeam
from speleodb.users.models import User
from speleodb.users.tests.factories import UserFactory


@pytest.fixture(scope="session", autouse=True)
def _load_test_env():
    project_base_dir = pathlib.Path(__file__).resolve().parent.parent
    if (env_file := project_base_dir / ".envs/test.env").exists():
        assert load_dotenv(env_file)


@pytest.fixture(autouse=True)
def _media_storage(settings, tmpdir) -> None:
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user(db) -> User:
    return UserFactory()


@pytest.fixture
def project(db) -> Project:
    return ProjectFactory()


@pytest.fixture
def team(db) -> SurveyTeam:
    return SurveyTeamFactory()


@pytest.fixture
def sha1_hash(db) -> str:
    import random
    import string
    from hashlib import sha1

    rand_str = "".join(random.sample(string.ascii_lowercase, 8))
    return sha1(rand_str.encode("utf-8")).hexdigest()  # noqa: S324


@pytest.fixture(autouse=True)
def cleanup_database(db):
    """
    Cleanup fixture that deletes all objects from the database after each test.
    Automatically applied to all tests that use the database.
    """
    yield  # Let the test run
    # Delete all objects from all models
    for model in apps.get_models():
        model.objects.all().delete()
