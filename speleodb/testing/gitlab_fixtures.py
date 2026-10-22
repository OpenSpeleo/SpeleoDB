"""Database-independent lifetime management for the four live repositories."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from django.test import override_settings

from speleodb.testing.gitlab_pool import get_pool
from speleodb.utils import gitlab_client

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


@pytest.fixture
def gitlab_retry_delays(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record elapsed backoff while keeping real HTTP and bounded attempts."""
    delays: list[float] = []
    # Only explicit absent-remote cases opt in. Replace this module's clock
    # reference, not process-wide time.sleep or any SDK/network response.
    monkeypatch.setattr(gitlab_client, "time", SimpleNamespace(sleep=delays.append))
    return delays
