"""Shared real GitLab resources for transport and repository integration tests."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING
from uuid import uuid4

import gitlab.exceptions
import pytest
from django.conf import settings

from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.surveys.models import Project

if TYPE_CHECKING:
    from collections.abc import Generator

    from gitlab import Gitlab


@pytest.fixture(name="live_gitlab")
def configured_gitlab_fixture() -> Generator[Gitlab]:
    """Require authenticated access to the configured integration namespace."""
    previous_client: Gitlab | None = GitlabManager._gl  # noqa: SLF001
    GitlabCredentials.get.cache_clear()
    GitlabManager._gl = None  # noqa: SLF001
    GitlabManager._get_project.cache_clear()  # noqa: SLF001
    try:
        GitlabManager._initialize()  # noqa: SLF001
        client: Gitlab | None = GitlabManager._gl  # noqa: SLF001
        assert client is not None
        assert client.user is not None
        group = client.groups.get(str(settings.GITLAB_GROUP_ID))
        assert group.full_path == settings.GITLAB_GROUP_NAME
        yield client
    finally:
        active_client: Gitlab | None = GitlabManager._gl  # noqa: SLF001
        if active_client is not None and active_client is not previous_client:
            active_client.session.close()
        GitlabManager._gl = previous_client  # noqa: SLF001
        GitlabManager._get_project.cache_clear()  # noqa: SLF001
        GitlabCredentials.get.cache_clear()


@pytest.fixture(name="live_project")
def disposable_project_fixture(live_gitlab: Gitlab) -> Generator[Project]:
    """Reserve a unique project name and remove only that test's remote."""
    project: Project = Project(id=uuid4())
    try:
        yield project
    finally:
        try:
            remote = live_gitlab.projects.get(
                f"{settings.GITLAB_GROUP_NAME}/{project.id}"
            )
        except gitlab.exceptions.GitlabGetError as error:
            if error.response_code != HTTPStatus.NOT_FOUND:
                raise
        else:
            remote.delete()
