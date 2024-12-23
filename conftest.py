#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--light",
        action="store_true",
        default=False,
        help="Skip on heavy duty tests - Namely those calling on git/gitlab",
    )


def pytest_runtest_setup(item):
    markers = [marker.name for marker in item.iter_markers()]
    if item.config.getoption("--light") and "skip_if_lighttest" in markers:
        pytest.skip("Skip GIT/GITLAB related tests to accelerate development")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "skip_if_lighttest: mark test to be skip in light test mode."
    )
