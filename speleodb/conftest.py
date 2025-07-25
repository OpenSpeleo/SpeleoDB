# -*- coding: utf-8 -*-

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest
from django.apps import apps
from dotenv import load_dotenv

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import SurveyTeamFactory
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from collections.abc import Generator

    from _pytest.compat import LEGACY_PATH
    from pytest_django.fixtures import SettingsWrapper

    from speleodb.surveys.models import Project
    from speleodb.users.models import SurveyTeam
    from speleodb.users.models import User


@pytest.fixture(scope="session", autouse=True)
def _load_test_env() -> None:
    project_base_dir = pathlib.Path(__file__).parents[1].resolve()
    if (env_file := project_base_dir / ".envs/test.env").exists():
        assert load_dotenv(env_file)


@pytest.fixture(autouse=True)
def _media_storage(settings: SettingsWrapper, tmpdir: LEGACY_PATH) -> None:
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user(db: None) -> User:
    return UserFactory.create()


@pytest.fixture
def admin_user(db: None) -> User:
    user = UserFactory.create(
        email="admin@example.com",
        is_staff=True,
        is_superuser=True,
    )
    assert user.is_superuser
    return user


@pytest.fixture
def project(db: None) -> Project:
    return ProjectFactory.create(created_by=UserFactory())


@pytest.fixture
def team(db: None) -> SurveyTeam:
    return SurveyTeamFactory.create()


@pytest.fixture(autouse=True)
def cleanup_database(db: None) -> Generator[None]:
    """
    Cleanup fixture that deletes all objects from the database after each test.
    Automatically applied to all tests that use the database.
    """
    yield  # Let the test run
    # Delete all objects from all models
    for model in apps.get_models():
        model.objects.all().delete()  # type: ignore[attr-defined]
