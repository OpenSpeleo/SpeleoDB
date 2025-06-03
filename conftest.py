#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.config.argparsing import Parser
    from _pytest.nodes import Item


# Note: This wait time is necessary because of django-countries sometimes being not
# ready. Simple workaround to fix the issue and barely noticeable.
def pytest_sessionstart(session: pytest.Session) -> None:
    """Hook to delay the start of the pytest session."""
    from django_countries import countries

    # Force loading the countries to avoid errors.
    # See: https://github.com/SmileyChris/django-countries/issues/472
    _ = countries.countries


def pytest_addoption(parser: Parser) -> None:
    """Add custom command-line options."""
    parser.addoption(
        "--light",
        action="store_true",
        default=False,
        help="Skip on heavy duty tests - Namely those calling on git/gitlab",
    )


def pytest_runtest_setup(item: Item) -> None:
    markers = [marker.name for marker in item.iter_markers()]
    if item.config.getoption("--light") and "skip_if_lighttest" in markers:
        pytest.skip("Skip GIT/GITLAB related tests to accelerate development")


def pytest_configure(config: Config) -> None:
    config.addinivalue_line(
        "markers", "skip_if_lighttest: mark test to be skip in light test mode."
    )
