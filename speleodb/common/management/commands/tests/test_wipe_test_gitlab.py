"""Exercise cleanup against real disposable GitLab subgroups and stdin pipes."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from django.conf import settings

from speleodb.git_engine.client import GitlabClient

if TYPE_CHECKING:
    from collections.abc import Generator

    from gitlab.v4.objects.groups import Group
    from gitlab.v4.objects.projects import Project

pytestmark = pytest.mark.skip_if_lighttest
BASE_DIR: Path = Path(__file__).resolve().parents[5]


@pytest.fixture
def cleanup_group() -> Generator[tuple[GitlabClient, Group, Project]]:
    client: GitlabClient = GitlabClient(
        f"{settings.GITLAB_HTTP_PROTOCOL}://{settings.GITLAB_HOST_URL}",
        private_token=settings.GITLAB_TOKEN,
        keep_base_url=settings.GITLAB_HTTP_PROTOCOL == "http",
    )
    name: str = f"cleanup-{uuid4().hex}"
    group: Group = client.groups.create(
        {"name": name, "path": name, "parent_id": settings.GITLAB_GROUP_ID}
    )
    try:
        project: Project = client.projects.create(
            {"name": "disposable", "namespace_id": group.id}
        )
        yield client, group, project
    finally:
        group.delete()
        client.session.close()


def run_cleanup(
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
    # Apply the command's group after Django has loaded its private dotenv.
    # Only the disposable subgroup is passed to this destructive command.
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


@pytest.mark.parametrize("answer", ["\nY\n", "N\nY\n", "invalid\nY\n", "yes\nY\n", ""])
def test_invalid_or_closed_confirmation_preserves_real_project(
    cleanup_group: tuple[GitlabClient, Group, Project], answer: str
) -> None:
    client, group, project = cleanup_group
    result: subprocess.CompletedProcess[str] = run_cleanup(group, answer=answer)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("Is this the correct group?") == 1
    assert client.projects.get(project.id).id == project.id


def test_explicit_confirmation_deletes_real_project(
    cleanup_group: tuple[GitlabClient, Group, Project],
) -> None:
    client, group, project = cleanup_group
    result: subprocess.CompletedProcess[str] = run_cleanup(group, answer=" y \n")
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("Is this the correct group?") == 1
    active_ids: list[int] = [
        item.id
        for item in client.groups.get(group.id).projects.list(iterator=True)
        if not item.attributes.get("marked_for_deletion_at")
    ]
    assert project.id not in active_ids


def test_dry_run_preserves_real_project(
    cleanup_group: tuple[GitlabClient, Group, Project],
) -> None:
    client, group, project = cleanup_group
    result: subprocess.CompletedProcess[str] = run_cleanup(
        group, answer="Y\n", delete=False
    )
    assert result.returncode == 0, result.stderr
    assert client.projects.get(project.id).id == project.id


def test_invalid_token_fails_command_and_preserves_real_project(
    cleanup_group: tuple[GitlabClient, Group, Project],
) -> None:
    client, group, project = cleanup_group
    result: subprocess.CompletedProcess[str] = run_cleanup(
        group, answer="Y\n", token=f"invalid-{uuid4()}"
    )
    assert result.returncode != 0
    assert "401" in result.stderr
    assert client.projects.get(project.id).id == project.id


@pytest.mark.parametrize("valid_token", [True, False])
def test_make_target_selects_test_settings(
    cleanup_group: tuple[GitlabClient, Group, Project],
    tmp_path: Path,
    valid_token: bool,
) -> None:
    client, group, project = cleanup_group
    # Keep the real test dotenv from overriding the disposable group's ID.
    # The Make target must also override an inherited settings module.
    (tmp_path / "manage.py").symlink_to(BASE_DIR / "manage.py")
    (tmp_path / "speleodb").symlink_to(BASE_DIR / "speleodb", target_is_directory=True)
    environment: dict[str, str] = os.environ.copy()
    token: str = settings.GITLAB_TOKEN if valid_token else f"invalid-{uuid4()}"
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "inherited_settings_must_not_be_used",
            "PYTHONPATH": str(BASE_DIR),
            "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
            "GITLAB_GROUP_ID": str(group.id),
            "GITLAB_GROUP_NAME": str(group.full_path),
            "GITLAB_HOST_URL": settings.GITLAB_HOST_URL,
            "GITLAB_TOKEN": token,
        }
    )
    # A scheduled cleanup must also succeed when a prior run marked the project.
    for _ in range(2 if valid_token else 1):
        result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
            ["make", "-f", str(BASE_DIR / "Makefile"), "wipe_gitlab_test"],  # noqa: S607
            cwd=tmp_path,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
        assert token not in result.stdout + result.stderr
        if valid_token:
            assert result.returncode == 0, result.stderr
            assert client.projects.get(project.id).marked_for_deletion_at
        else:
            assert result.returncode != 0
            assert "GitlabAuthenticationError (HTTP 401)" in result.stderr
            assert not client.projects.get(project.id).marked_for_deletion_at
