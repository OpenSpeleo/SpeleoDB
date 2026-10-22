# -*- coding: utf-8 -*-

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest
from django.test.client import Client
from dotenv import load_dotenv

from speleodb.api.v2.tests.factories import SurveyTeamFactory
from speleodb.testing.gitlab_pool import canonical_project
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from _pytest.compat import LEGACY_PATH
    from pytest_django.fixtures import Settings

    from speleodb.surveys.models import Project
    from speleodb.users.models import SurveyTeam
    from speleodb.users.models import User


@pytest.fixture(scope="session", autouse=True)
def _load_test_env() -> None:
    project_base_dir = pathlib.Path(__file__).parents[1].resolve()
    if (env_file := project_base_dir / ".envs/test.env").exists():
        assert load_dotenv(env_file)


@pytest.fixture(autouse=True)
def _media_storage(settings: Settings, tmpdir: LEGACY_PATH) -> None:
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
def staff_user(db: None) -> User:
    user = UserFactory.create(
        email="staff@example.com",
        is_staff=True,
        is_superuser=False,
    )
    assert user.is_staff
    assert not user.is_superuser
    return user


@pytest.fixture
def staff_client(staff_user: User) -> Client:

    client = Client()
    client.force_login(staff_user)
    return client


@pytest.fixture
def project(db: None, user: User) -> Project:
    return canonical_project(created_by=user.email)


@pytest.fixture
def team(db: None) -> SurveyTeam:
    return SurveyTeamFactory.create()
