"""Git explorer timestamps preserve real repository instants at every nesting level."""

from __future__ import annotations

import datetime as dt

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.git_engine.core import GitFile
from speleodb.testing.gitlab_pool import canonical_project
from speleodb.testing.gitlab_pool import canonical_user
from speleodb.testing.gitlab_pool import get_pool


@pytest.mark.django_db
def test_git_explorer_preserves_top_level_and_file_commit_instants() -> None:
    user = canonical_user("A")
    project = canonical_project(PermissionLevel.ADMIN)
    UserProjectPermissionFactory.create(
        project=project, target=user, level=PermissionLevel.ADMIN
    )
    get_pool().prepare(project)
    repository = project.git_repo
    (repository.path / "notes.txt").write_text(
        "Revision timestamp fixture", encoding="utf-8"
    )
    project.commit_and_push_project("Add revision notes", author=user)
    commit = repository.head.commit
    expected_files = {
        str(item.path): (item.commit.authored_date, item.commit.committed_date)
        for item in commit.tree.traverse()
        if isinstance(item, GitFile)
    }
    # A tiny real project file exercises nested commits without another remote
    # allocation; the shared pool restores this revision after the test.
    assert expected_files
    client = APIClient()
    client.force_authenticate(user)
    with timezone.override("Europe/Prague"):
        response = client.get(
            reverse(
                "api:v2:project-gitexplorer",
                kwargs={"id": project.id, "hexsha": commit.hexsha},
            )
        )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["commit"]["hexsha"] == commit.hexsha
    assert {item["path"] for item in data["files"]} == set(expected_files)
    revisions = [
        (data["commit"], (commit.authored_date, commit.committed_date)),
        *((item["commit"], expected_files[item["path"]]) for item in data["files"]),
    ]
    for revision, expected in revisions:
        for field, epoch in zip(
            ("authored_date", "committed_date"), expected, strict=True
        ):
            value = revision[field]
            assert value.endswith("Z")
            assert dt.datetime.fromisoformat(value).timestamp() == epoch
