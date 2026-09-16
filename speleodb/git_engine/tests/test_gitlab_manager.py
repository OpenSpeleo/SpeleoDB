"""Repository creation and cloning through the configured real GitLab service."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any
from uuid import uuid4

import gitlab.exceptions
import pytest
from django.conf import settings
from django.test import override_settings

from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabError
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.git_engine.tests.live_gitlab import (
    configured_gitlab_fixture,  # noqa: F401
)
from speleodb.git_engine.tests.live_gitlab import (
    disposable_project_fixture,  # noqa: F401
)
from speleodb.testing.gitlab_audit import creation_allocation
from speleodb.testing.gitlab_pool import get_pool

if TYPE_CHECKING:
    from pathlib import Path

    from gitlab import Gitlab
    from requests import Response

    from speleodb.surveys.models import Project

pytestmark = pytest.mark.skip_if_lighttest


def test_existing_remote_is_cloned_without_an_extra_commit(
    live_gitlab: Gitlab, tmp_path: Path
) -> None:
    live_project: Project = get_pool().model()
    get_pool().prepare(live_project)
    original = GitlabManager.create_or_clone_project(live_project, tmp_path / "first")
    assert original is not None
    try:
        original_sha: str = original.head.commit.hexsha
    finally:
        original.close()

    requests: list[str] = []

    def observe(response: Response, **kwargs: Any) -> None:
        requests.append(str(response.request.method))

    live_gitlab.session.hooks["response"].append(observe)
    try:
        cloned = GitlabManager.create_or_clone_project(
            live_project, tmp_path / "second"
        )
    finally:
        live_gitlab.session.hooks["response"].remove(observe)
    # A transient server error may require bounded lookup retries. Every
    # request must still be a lookup; an existing remote never needs a POST.
    assert requests
    assert all(method == "GET" for method in requests)
    assert cloned is not None
    try:
        assert cloned.head.commit.hexsha == original_sha
        assert not cloned.is_dirty(untracked_files=True)
        remote = live_gitlab.projects.get(
            f"{settings.GITLAB_GROUP_NAME}/{live_project.id}"
        )
        assert len(remote.commits.list(get_all=True)) == 1
    finally:
        cloned.close()


def test_invalid_namespace_does_not_create_local_repository(
    live_gitlab: Gitlab, live_project: Project, tmp_path: Path
) -> None:
    namespace: str = "-1"
    with override_settings(GITLAB_GROUP_ID=namespace):
        GitlabCredentials.get.cache_clear()
        try:
            with (
                creation_allocation(
                    "invalid-namespace", namespace, str(live_project.id), negative=True
                ),
                pytest.raises(gitlab.exceptions.GitlabCreateError) as raised,
            ):
                GitlabManager.create_or_clone_project(live_project, tmp_path)
        finally:
            GitlabCredentials.get.cache_clear()

    assert raised.value.response_code == HTTPStatus.BAD_REQUEST
    # GitLab versions describe invalid namespace IDs with different error payloads.
    assert raised.value.error_message
    assert not (tmp_path / str(live_project.id)).exists()
    with pytest.raises(gitlab.exceptions.GitlabGetError) as absent:
        live_gitlab.projects.get(f"{settings.GITLAB_GROUP_NAME}/{live_project.id}")
    assert absent.value.response_code == HTTPStatus.NOT_FOUND


def test_invalid_token_fails_before_repository_initialization(
    live_gitlab: Gitlab, live_project: Project, tmp_path: Path
) -> None:
    # Authenticate the real configured token in fixture setup before testing a
    # genuinely invalid credential. An unavailable service cannot satisfy setup.
    with override_settings(GITLAB_TOKEN=f"invalid-{uuid4()}"):
        GitlabManager._gl = None  # noqa: SLF001
        GitlabCredentials.get.cache_clear()
        try:
            with pytest.raises(GitlabError) as raised:
                GitlabManager.create_or_clone_project(live_project, tmp_path)
        finally:
            GitlabCredentials.get.cache_clear()
            GitlabManager._gl = live_gitlab  # noqa: SLF001

    assert isinstance(
        raised.value.__cause__, gitlab.exceptions.GitlabAuthenticationError
    )
    assert raised.value.__cause__.response_code == HTTPStatus.UNAUTHORIZED
    assert not (tmp_path / str(live_project.id)).exists()
