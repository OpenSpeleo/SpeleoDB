"""Creation and deletion coverage with one repository per complete lifecycle."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING
from uuid import uuid4

import gitlab.exceptions
import pytest
from django.conf import settings
from django.core.management import call_command
from django.test import override_settings

from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.git_engine.tests.live_gitlab import (
    configured_gitlab_fixture,  # noqa: F401
)
from speleodb.surveys.models import Project
from speleodb.testing.gitlab_audit import creation_allocation
from speleodb.testing.gitlab_lifecycle import assert_group_cleanup_lifecycle
from speleodb.testing.gitlab_lifecycle import assert_remote_deleted
from speleodb.testing.gitlab_lifecycle import cleanup_remote_on_exit
from speleodb.testing.gitlab_lifecycle import delete_remote_if_present
from speleodb.testing.gitlab_lifecycle import isolated_gitlab_group

if TYPE_CHECKING:
    from pathlib import Path

    from gitlab import Gitlab
    from gitlab.v4.objects.projects import Project as RemoteProject

    from speleodb.users.models import User

pytestmark = pytest.mark.skip_if_lighttest


@pytest.mark.django_db
def test_new_repository_cache_recovery_and_user_cleanup(
    live_gitlab: Gitlab, user: User, tmp_path: Path
) -> None:
    project: Project = ProjectFactory.create(created_by=user.email)
    UserProjectPermissionFactory.create(
        target=user, project=project, level=PermissionLevel.ADMIN
    )
    remote_path: str = f"{settings.GITLAB_GROUP_NAME}/{project.id}"
    try:
        assert GitlabManager.get_commit_history(project) is None
        assert GitlabManager.get_last_commit_hash(project) is None
        with creation_allocation(
            "manager-new", settings.GITLAB_GROUP_ID, str(project.id)
        ):
            repository = GitlabManager.create_or_clone_project(project, tmp_path)
        assert repository is not None
        try:
            assert repository.head.is_valid()
            assert repository.active_branch.name == settings.DJANGO_GIT_BRANCH_NAME
            remote: RemoteProject = live_gitlab.projects.get(remote_path)
            branch = remote.branches.get(settings.DJANGO_GIT_BRANCH_NAME)
            assert branch.commit["id"] == repository.head.commit.hexsha
            assert repository.head.commit.message.strip() == (
                settings.DJANGO_GIT_FIRST_COMMIT_MESSAGE
            )
            assert len(remote.commits.list(get_all=True)) == 1
            history = GitlabManager.get_commit_history(project)
            assert history is not None
            assert [commit["id"] for commit in history] == [
                repository.head.commit.hexsha
            ]
            assert all("web_url" not in commit for commit in history)
            assert GitlabManager.get_last_commit_hash(project) == (
                repository.head.commit.hexsha
            )
        finally:
            repository.close()

        with override_settings(GITLAB_TOKEN=f"invalid-{uuid4()}"):
            GitlabCredentials.get.cache_clear()
            try:
                with pytest.raises(
                    gitlab.exceptions.GitlabAuthenticationError
                ) as raised:
                    call_command(
                        "wipe_test_user_projects",
                        user_email=user.email,
                        skip_user_confirmation=True,
                    )
            finally:
                GitlabCredentials.get.cache_clear()
                GitlabManager._gl = live_gitlab  # noqa: SLF001
        assert raised.value.response_code == HTTPStatus.UNAUTHORIZED
        assert Project.objects.filter(id=project.id).exists()
        assert live_gitlab.projects.get(remote.id).id == remote.id

        call_command(
            "wipe_test_user_projects",
            user_email=user.email,
            skip_user_confirmation=True,
        )
        assert not Project.objects.filter(id=project.id).exists()
        assert_remote_deleted(live_gitlab, remote.id)
    finally:
        try:
            remaining: RemoteProject = live_gitlab.projects.get(remote_path)
        except gitlab.exceptions.GitlabGetError as error:
            if error.response_code != HTTPStatus.NOT_FOUND:
                raise
        else:
            delete_remote_if_present(live_gitlab, remaining.id)


def test_empty_repository_initialization_and_group_cleanup(
    live_gitlab: Gitlab, tmp_path: Path
) -> None:
    project: Project = Project(id=uuid4())
    with isolated_gitlab_group(live_gitlab) as group:
        with creation_allocation("manager-empty", group.id, str(project.id)):
            remote: RemoteProject = live_gitlab.projects.create(
                {"name": str(project.id), "namespace_id": group.id}
            )
        assert remote.empty_repo
        repository = GitlabManager.create_or_clone_project(project, tmp_path)
        assert repository is not None
        try:
            branch = remote.branches.get(settings.DJANGO_GIT_BRANCH_NAME)
            assert branch.commit["id"] == repository.head.commit.hexsha
            assert len(remote.commits.list(get_all=True)) == 1
        finally:
            repository.close()
        assert_group_cleanup_lifecycle(live_gitlab, group, remote)


def test_cleanup_preserves_original_failure_when_remote_was_never_created(
    live_gitlab: Gitlab,
) -> None:
    failure: RuntimeError = RuntimeError("Creation did not reach GitLab")
    with (
        pytest.raises(RuntimeError) as raised,
        cleanup_remote_on_exit(live_gitlab, f"{settings.GITLAB_GROUP_NAME}/{uuid4()}"),
    ):
        raise failure
    assert raised.value is failure
