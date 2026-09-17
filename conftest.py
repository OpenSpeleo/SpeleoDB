#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.core.cache import cache

if TYPE_CHECKING:
    from collections.abc import Generator

    from _pytest.config import Config
    from _pytest.config.argparsing import Parser
    from _pytest.nodes import Item

    from speleodb.users.models import User


pytest_plugins: tuple[str, ...] = (
    "speleodb.testing.pytest_gitlab",
    "speleodb.testing.gitlab_fixtures",
)


@pytest.fixture
def admin_user(db: None, django_user_model: type[User]) -> User:
    """Preserve pytest-django's admin defaults with a required display name."""
    try:
        return django_user_model.objects.get_by_natural_key("admin@example.com")
    except django_user_model.DoesNotExist:
        return django_user_model.objects.create_superuser(
            email="admin@example.com",
            password="password",  # noqa: S106
            name="Test Administrator",
        )


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items: list[Item]) -> None:
    from django_countries import countries  # noqa: PLC0415

    # Force loading the countries to avoid errors.
    # See: https://github.com/SmileyChris/django-countries/issues/472
    from django_countries.data import COUNTRIES  # noqa: F401, PLC0415

    assert len(countries.countries) > 0


def pytest_addoption(parser: Parser) -> None:
    """Add custom command-line options."""
    parser.addoption(
        "--light",
        action="store_true",
        default=False,
        help="Skip on heavy duty tests - Namely those calling on git/gitlab",
    )

    parser.addoption(
        "--offline",
        action="store_true",
        default=False,
        help="Skip on tests that can only be executed with a network connection",
    )


def pytest_runtest_setup(item: Item) -> None:
    markers = [marker.name for marker in item.iter_markers()]
    if item.config.getoption("--light") and "skip_if_lighttest" in markers:
        pytest.skip("Skip GIT/GITLAB related tests to accelerate development ...")

    if item.config.getoption("--offline") and "skip_if_offline" in markers:
        pytest.skip("Skip - This test needs an internet connection ...")


def pytest_configure(config: Config) -> None:
    config.addinivalue_line(
        "markers", "skip_if_lighttest: mark test to be skip in light test mode."
    )
    config.addinivalue_line(
        "markers", "skip_if_offline: mark test to be skip in offline test mode."
    )


@pytest.fixture(autouse=True)
def clear_cache_between_tests() -> Generator[None]:
    """Fixture to clear the Django cache after each test function runs."""
    yield

    # Clear django cache after the yield runs as teardown
    cache.clear()
