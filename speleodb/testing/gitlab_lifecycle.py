"""Real GitLab lifecycle assertions that share one sacrificial repository."""

from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from uuid import uuid4

import gitlab.exceptions
import pytest
from django.conf import settings
from django.test import override_settings

from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.testing.gitlab_audit import record_cleanup

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator

    from gitlab import Gitlab
    from gitlab.v4.objects.groups import Group
    from gitlab.v4.objects.projects import Project as RemoteProject
    from requests import Response

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
    group: Group, *, answer: str = "", delete: bool = True, token: str | None = None
) -> subprocess.CompletedProcess[str]:
    environment: dict[str, str] = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.test",
            "CLEANUP_GROUP_ID": str(group.id),
            "CLEANUP_GROUP_NAME": str(group.full_path),
            "CLEANUP_HOST": settings.GITLAB_HOST_URL,
            "CLEANUP_TOKEN": settings.GITLAB_TOKEN if token is None else token,
            "CLEANUP_DELETE": "1" if delete else "0",
        }
    )
    script: str = """
import os
import django
from django.core.management import call_command
django.setup()
for key, source in {
    "GITLAB_GROUP_ID": "CLEANUP_GROUP_ID",
    "GITLAB_GROUP_NAME": "CLEANUP_GROUP_NAME",
    "GITLAB_HOST_URL": "CLEANUP_HOST",
    "GITLAB_TOKEN": "CLEANUP_TOKEN",
}.items():
    os.environ[key] = os.environ[source]
call_command("wipe_test_gitlab", accept_danger=os.environ["CLEANUP_DELETE"] == "1")
"""
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=BASE_DIR,
        env=environment,
        input=answer,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


def assert_group_cleanup_lifecycle(
    client: Gitlab, group: Group, remote: RemoteProject
) -> None:
    """Preserve a remote through rejected confirmations, then delete it once."""
    for answer in ("\nY\n", "N\nY\n", "invalid\nY\n", "yes\nY\n", ""):
        result: subprocess.CompletedProcess[str] = run_group_cleanup(
            group, answer=answer
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.count("Is this the correct group?") == 1
        assert client.projects.get(remote.id).id == remote.id

    result = run_group_cleanup(group, answer="Y\n", delete=False)
    assert result.returncode == 0, result.stderr
    assert client.projects.get(remote.id).id == remote.id

    result = run_group_cleanup(group, answer="Y\n", token=f"invalid-{uuid4()}")
    assert result.returncode != 0
    assert "401" in result.stderr
    assert client.projects.get(remote.id).id == remote.id

    result = run_group_cleanup(group, answer=" y \n")
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("Is this the correct group?") == 1
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
    """Exercise the actual Make entrypoint before and after its first deletion."""
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
    for valid_token in (False, True, True):
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


def assert_initial_commit_lifecycle(
    remote: RemoteProject,
    client: Gitlab,
    *,
    create_initial_commit: Callable[[RemoteProject], str],
    max_attempts: int,
) -> None:
    """Initialize one real empty remote, then prove duplicate creation is rejected."""
    responses: list[Response] = []

    def observe(response: Response, **kwargs: Any) -> None:
        if response.request.method == "POST" and response.request.path_url.endswith(
            "/repository/commits"
        ):
            responses.append(response)

    client.session.hooks["response"].append(observe)
    try:
        initial_sha: str = create_initial_commit(remote)
        assert 1 <= len(responses) <= max_attempts
        assert responses[-1].status_code == HTTPStatus.CREATED
        assert all(
            response.status_code == HTTPStatus.NOT_FOUND for response in responses[:-1]
        )
        assert all(
            "PRIVATE-TOKEN" in response.request.headers for response in responses
        )
        initial = remote.commits.get(initial_sha)
        assert initial.message.strip() == "Historic survey"
        assert remote.branches.get("main").commit["id"] == initial_sha
        assert remote.files.get("survey.txt", ref=initial_sha).decode() == (
            b"historic data"
        )
        assert len(remote.commits.list(get_all=True)) == 1

        responses.clear()
        with pytest.raises(gitlab.exceptions.GitlabCreateError) as raised:
            create_initial_commit(remote)
        assert raised.value.response_code == HTTPStatus.BAD_REQUEST
        assert len(responses) == 1
        assert "already exists" in str(raised.value.error_message).lower()
        assert [commit.id for commit in remote.commits.list(get_all=True)] == [
            initial_sha
        ]
    finally:
        client.session.hooks["response"].remove(observe)
