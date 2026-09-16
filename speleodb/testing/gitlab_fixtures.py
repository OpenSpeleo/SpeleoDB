"""Database-independent lifetime management for the four live repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.test import override_settings

from speleodb.testing.gitlab_pool import get_pool

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture(scope="session", autouse=True)
def _gitlab_pool_lifetime() -> Generator[None]:
    yield
    get_pool().close()
    get_pool.cache_clear()


@pytest.fixture(autouse=True)
def _gitlab_test_lease(tmp_path: Path) -> Generator[None]:
    pool = get_pool()
    with override_settings(DJANGO_GIT_PROJECTS_DIR=tmp_path / "git-projects"):
        try:
            yield
        finally:
            pool.release()
