"""Real GitLab lifecycle assertions that share one sacrificial repository."""

from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from contextlib import redirect_stdout
from http import HTTPStatus
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import uuid4

import gitlab.exceptions
import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.testing.gitlab_audit import record_cleanup

if TYPE_CHECKING:
    from collections.abc import Iterator

    from gitlab import Gitlab
    from gitlab.v4.objects.groups import Group
    from gitlab.v4.objects.projects import Project as RemoteProject

BASE_DIR: Path = Path(__file__).resolve().parents[2]


@contextmanager
def isolated_gitlab_group(client: Gitlab) -> Iterator[Group]:
    """Scope destructive checks to a fresh subgroup, including cached settings."""
    name: str = f"lifecycle-{uuid4().hex}"
    group: Group = client.groups.create(
        {"name": name, "path": name, "parent_id": settings.GITLAB_GROUP_ID}
    )
    previous_client: Gitlab | None = GitlabManager._gl  # noqa: SLF001
    try:
        with override_settings(
            GITLAB_GROUP_ID=str(group.id), GITLAB_GROUP_NAME=group.full_path
        ):
            GitlabCredentials.get.cache_clear()
            GitlabManager._get_project.cache_clear()  # noqa: SLF001
            GitlabManager._gl = client  # noqa: SLF001
            try:
                yield group
            finally:
                active_client: Gitlab | None = GitlabManager._gl  # noqa: SLF001
                if active_client is not None and active_client not in (
                    client,
                    previous_client,
                ):
                    active_client.session.close()
                GitlabManager._gl = previous_client  # noqa: SLF001
                GitlabManager._get_project.cache_clear()  # noqa: SLF001
                GitlabCredentials.get.cache_clear()
    finally:
        # A failed lifecycle may not reach its terminal command. Delete and
        # verify each remaining child explicitly instead of assuming that the
        # subgroup's asynchronous deletion has already removed repositories.
        for project in group.projects.list(iterator=True):
            delete_remote_if_present(client, project.id)
        group.delete()


def assert_remote_deleted(client: Gitlab, remote_id: int) -> None:
    """Accept GitLab's actual immediate or delayed deletion outcome."""
    try:
        current: RemoteProject = client.projects.get(remote_id)
    except gitlab.exceptions.GitlabGetError as error:
        if error.response_code != HTTPStatus.NOT_FOUND:
            raise
        record_cleanup(remote_id, "verified-absent")
    else:
        assert current.attributes.get("marked_for_deletion_at")
        record_cleanup(remote_id, "verified-marked-for-deletion")


def delete_remote_if_present(client: Gitlab, remote_id: int) -> None:
    """Cleanup never retries deletion of a repository already marked for removal."""
    try:
        current: RemoteProject = client.projects.get(remote_id)
    except gitlab.exceptions.GitlabGetError as error:
        if error.response_code != HTTPStatus.NOT_FOUND:
            raise
        record_cleanup(remote_id, "verified-absent")
    else:
        if not current.attributes.get("marked_for_deletion_at"):
            current.delete()
        assert_remote_deleted(client, remote_id)


@contextmanager
def cleanup_remote_on_exit(client: Gitlab, project_path: str) -> Iterator[None]:
    """Own an exact remote path before creation can lose its response.

    Looking up the preallocated identity also lets the audit reconcile a POST
    that reached GitLab but failed before the caller received its project ID.
    """
    try:
        yield
    finally:
        try:
            remote: RemoteProject = client.projects.get(project_path)
        except gitlab.exceptions.GitlabGetError as error:
            if error.response_code != HTTPStatus.NOT_FOUND:
                raise
        else:
            delete_remote_if_present(client, int(remote.id))


def run_group_cleanup(
    group: Group,
    *,
    answer: str = "",
    delete: bool = True,
    token: str | None = None,
    older_than_hours: int | None = None,
    skip_user_confirmation: bool = False,
) -> str:
    """Run the real command and HTTP requests without another Django startup."""
    environment: dict[str, str] = {
        "GITLAB_GROUP_ID": str(group.id),
        "GITLAB_GROUP_NAME": str(group.full_path),
        "GITLAB_HOST_URL": settings.GITLAB_HOST_URL,
        "GITLAB_TOKEN": settings.GITLAB_TOKEN if token is None else token,
    }
    output = StringIO()
    # Only process input is substituted. The command, confirmation parser and
    # GitLab transport stay real. Restore the entire environment mapping so
    # dotenv additions cannot leak; inherited audit attribution stays intact.
    with (
        patch.dict(os.environ, environment),
        patch.object(sys, "stdin", StringIO(answer)),
        redirect_stdout(output),
    ):
        call_command(
            "wipe_test_gitlab",
            accept_danger=delete,
            older_than_hours=older_than_hours,
            skip_user_confirmation=skip_user_confirmation,
            stdout=output,
        )
    return output.getvalue()


def assert_group_cleanup_lifecycle(
    client: Gitlab, group: Group, remote: RemoteProject
) -> None:
    """Preserve a remote through rejected confirmations, then delete it once."""
    # The standalone confirm_command stdin tests cover every accepted/rejected
    # spelling and EOF. Keep one real Django command case proving a rejected
    # answer cannot consume a later Y and delete the remote.
    output: str = run_group_cleanup(group, answer="invalid\nY\n")
    assert output.count("Is this the correct group?") == 1
    assert not client.projects.get(remote.id).attributes.get("marked_for_deletion_at")

    run_group_cleanup(group, answer="Y\n", delete=False)
    assert not client.projects.get(remote.id).attributes.get("marked_for_deletion_at")

    run_group_cleanup(group, answer="Y\n", older_than_hours=24)
    assert not client.projects.get(remote.id).attributes.get("marked_for_deletion_at")

    with pytest.raises(CommandError, match=r"GitlabAuthenticationError \(HTTP 401\)"):
        run_group_cleanup(group, answer="Y\n", token=f"invalid-{uuid4()}")
    assert not client.projects.get(remote.id).attributes.get("marked_for_deletion_at")

    output = run_group_cleanup(group, answer=" y \n")
    assert output.count("Is this the correct group?") == 1
    assert_remote_deleted(client, remote.id)
    active_ids: list[int] = [
        item.id
        for item in client.groups.get(group.id).projects.list(iterator=True)
        if not item.attributes.get("marked_for_deletion_at")
    ]
    assert remote.id not in active_ids


def assert_make_cleanup_lifecycle(
    client: Gitlab, group: Group, remote: RemoteProject, tmp_path: Path
) -> None:
    """Exercise Make settings/authentication, then real command idempotency."""
    (tmp_path / "manage.py").symlink_to(BASE_DIR / "manage.py")
    (tmp_path / "speleodb").symlink_to(BASE_DIR / "speleodb", target_is_directory=True)
    environment: dict[str, str] = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "inherited_settings_must_not_be_used",
            "PYTHONPATH": str(BASE_DIR),
            "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
            "GITLAB_GROUP_ID": str(group.id),
            "GITLAB_GROUP_NAME": str(group.full_path),
            "GITLAB_HOST_URL": settings.GITLAB_HOST_URL,
        }
    )
    for valid_token in (False, True):
        token: str = settings.GITLAB_TOKEN if valid_token else f"invalid-{uuid4()}"
        environment["GITLAB_TOKEN"] = token
        result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
            ["make", "-f", str(BASE_DIR / "Makefile"), "wipe_gitlab_test"],  # noqa: S607
            cwd=tmp_path,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
        token_was_printed: bool = token in result.stdout + result.stderr
        assert not token_was_printed
        if valid_token:
            assert result.returncode == 0, result.stderr
            assert_remote_deleted(client, remote.id)
        else:
            assert result.returncode != 0
            assert "GitlabAuthenticationError (HTTP 401)" in result.stderr
            assert not client.projects.get(remote.id).marked_for_deletion_at

    # The two subprocesses cover Make's settings and flag wiring. Repeating the
    # real command covers already-deleted handling without a third Django start.
    run_group_cleanup(group, skip_user_confirmation=True)
    assert_remote_deleted(client, remote.id)
