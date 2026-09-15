"""User cleanup preserves database records unless real GitLab deletion succeeds."""

from __future__ import annotations

import socket
import subprocess
import sys
from http import HTTPStatus
from typing import TYPE_CHECKING
from uuid import uuid4

import gitlab.exceptions
import pytest
from django.core.management import call_command
from django.test import override_settings
from requests.exceptions import ConnectionError as RequestsConnectionError

from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.git_engine.tests.live_gitlab import (
    configured_gitlab_fixture,  # noqa: F401
)
from speleodb.surveys.models import Project

if TYPE_CHECKING:
    from collections.abc import Generator

    from gitlab import Gitlab
    from gitlab.v4.objects.projects import Project as RemoteProject

    from speleodb.users.models import User

pytestmark = pytest.mark.skip_if_lighttest


@pytest.fixture
def owned_project(project: Project, user: User) -> Project:
    UserProjectPermissionFactory.create(
        target=user, project=project, level=PermissionLevel.ADMIN
    )
    return project


@pytest.fixture
def remote_project(
    owned_project: Project, live_gitlab: Gitlab
) -> Generator[RemoteProject]:
    credentials: GitlabCredentials = GitlabCredentials.get()
    remote: RemoteProject = live_gitlab.projects.create(
        {"name": str(owned_project.id), "namespace_id": credentials.group_id}
    )
    try:
        yield remote
    finally:
        try:
            current: RemoteProject = live_gitlab.projects.get(remote.id)
        except gitlab.exceptions.GitlabGetError as error:
            if error.response_code != HTTPStatus.NOT_FOUND:
                raise
        else:
            if not current.attributes.get("marked_for_deletion_at"):
                current.delete()


def run_cleanup(user: User) -> None:
    call_command(
        "wipe_test_user_projects",
        user_email=user.email,
        skip_user_confirmation=True,
    )


def test_successful_remote_deletion_removes_local_project(
    user: User,
    owned_project: Project,
    remote_project: RemoteProject,
    live_gitlab: Gitlab,
) -> None:
    run_cleanup(user)
    assert not Project.objects.filter(id=owned_project.id).exists()
    try:
        current: RemoteProject = live_gitlab.projects.get(remote_project.id)
    except gitlab.exceptions.GitlabGetError as error:
        if error.response_code != HTTPStatus.NOT_FOUND:
            raise
    else:
        assert current.attributes.get("marked_for_deletion_at")


def test_confirmed_missing_remote_removes_local_project(
    user: User,
    owned_project: Project,
    live_gitlab: Gitlab,
) -> None:
    credentials: GitlabCredentials = GitlabCredentials.get()
    with pytest.raises(gitlab.exceptions.GitlabGetError) as absent:
        live_gitlab.projects.get(f"{credentials.group_name}/{owned_project.id}")
    assert absent.value.response_code == HTTPStatus.NOT_FOUND
    run_cleanup(user)
    assert not Project.objects.filter(id=owned_project.id).exists()


def test_authentication_failure_preserves_local_and_remote_project(
    user: User,
    owned_project: Project,
    remote_project: RemoteProject,
    live_gitlab: Gitlab,
) -> None:
    with override_settings(GITLAB_TOKEN=f"invalid-{uuid4()}"):
        GitlabCredentials.get.cache_clear()
        try:
            with pytest.raises(gitlab.exceptions.GitlabAuthenticationError) as raised:
                run_cleanup(user)
        finally:
            GitlabCredentials.get.cache_clear()
            GitlabManager._gl = live_gitlab  # noqa: SLF001
    assert raised.value.response_code == HTTPStatus.UNAUTHORIZED
    assert Project.objects.filter(id=owned_project.id).exists()
    assert live_gitlab.projects.get(remote_project.id).id == remote_project.id


def test_transport_failure_preserves_local_project(
    user: User,
    owned_project: Project,
    live_gitlab: Gitlab,
) -> None:
    with socket.socket() as unavailable:
        unavailable.bind(("127.0.0.1", 0))
        port: int = unavailable.getsockname()[1]
        with override_settings(
            GITLAB_HOST_URL=f"127.0.0.1:{port}",
            GITLAB_HTTP_PROTOCOL="http",
            DJANGO_GIT_RETRY_ATTEMPTS=1,
        ):
            GitlabCredentials.get.cache_clear()
            try:
                with pytest.raises(RequestsConnectionError):
                    run_cleanup(user)
            finally:
                GitlabCredentials.get.cache_clear()
                GitlabManager._gl = live_gitlab  # noqa: SLF001
    assert Project.objects.filter(id=owned_project.id).exists()


@pytest.mark.parametrize(
    ("answer", "confirmed"),
    [
        ("\nY\n", False),
        ("invalid\nY\n", False),
        ("N\nY\n", False),
        ("yes\nY\n", False),
        ("", False),
        (" y \n", True),
    ],
)
def test_shared_confirmation_reads_exactly_one_real_stdin_answer(
    answer: str,
    confirmed: bool,
) -> None:
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            "-c",
            "from speleodb.utils.confirmation import confirm_command; "
            "print(confirm_command('Confirm? '))",
        ],
        input=answer,
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    )
    assert result.stdout == f"Confirm? {confirmed}\n"
