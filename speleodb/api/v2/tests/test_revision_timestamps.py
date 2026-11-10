"""Revision timestamps preserve instants through storage and API composition."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import git
import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v2.serializers.git import GitCommitSerializer
from speleodb.api.v2.serializers.project_commit import ProjectCommitSerializer
from speleodb.api.v2.tests.factories import ProjectCommitFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.git_engine.core import GitCommit
from speleodb.testing.gitlab_pool import canonical_user

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.django_db
@pytest.mark.parametrize("zone", ["UTC", "America/New_York", "Europe/Prague"])
def test_cached_revision_preserves_instants(zone: str) -> None:
    # The repeated New York hour must remain two distinct instants; summer
    # also exercises the different daylight-saving offset.
    dates = [
        dt.datetime(
            2026, 11, 1, 1, 30, 17, 123456, ZoneInfo("America/New_York"), fold=0
        ),
        dt.datetime(
            2026, 11, 1, 1, 30, 17, 123456, ZoneInfo("America/New_York"), fold=1
        ),
        dt.datetime(2026, 7, 1, 12, 30, 17, 123456, ZoneInfo("Europe/Prague")),
    ]
    with timezone.override(zone):
        for authored in dates:
            commit = ProjectCommitFactory.create(authored_date=authored)
            commit.refresh_from_db()
            value = ProjectCommitSerializer(commit).data["authored_date"]
            assert value.endswith("Z")
            assert dt.datetime.fromisoformat(value) == authored.astimezone(dt.UTC)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("minutes", "expected"), [(-2.5, "2 minutes ago"), (2.5, "in 2 minutes")]
)
def test_cached_revision_age_retains_timezone(minutes: float, expected: str) -> None:
    with override_settings(TIME_ZONE="America/New_York"):
        commit = ProjectCommitFactory.create(
            authored_date=timezone.now() + dt.timedelta(minutes=minutes)
        )
        commit.refresh_from_db()
        assert ProjectCommitSerializer(commit).data["dt_since"] == expected


@pytest.mark.parametrize("zone", ["UTC", "America/New_York", "Europe/Prague"])
def test_git_revision_preserves_author_and_committer_instants(
    tmp_path: Path, zone: str
) -> None:
    authored = timezone.now() - dt.timedelta(days=2)
    committed = timezone.now() - dt.timedelta(minutes=2.5)
    with git.Repo.init(tmp_path / "repository", bare=True) as repository:
        commit = GitCommit(
            repository,
            bytes.fromhex("a" * 40),
            author=git.Actor("Author", "author@example.com"),
            authored_date=int(authored.timestamp()),
            author_tz_offset=-7200,
            committer=git.Actor("Committer", "committer@example.com"),
            committed_date=int(committed.timestamp()),
            committer_tz_offset=18000,
            message="Distinct author and committer dates",
            parents=[],
        )
        with timezone.override(zone):
            data = GitCommitSerializer(commit).data
        for field, original in (
            ("authored_date", authored),
            ("committed_date", committed),
        ):
            assert data[field].endswith("Z")
            assert dt.datetime.fromisoformat(data[field]).timestamp() == int(
                original.timestamp()
            )
        assert data["dt_since"] == "2 minutes ago"


@pytest.mark.django_db
def test_revision_and_project_list_responses_preserve_cached_timestamp() -> None:
    user = canonical_user("A")
    authored = timezone.now() - dt.timedelta(minutes=2.5)
    commit = ProjectCommitFactory.create(authored_date=authored)
    UserProjectPermissionFactory.create(
        project=commit.project, target=user, level=PermissionLevel.ADMIN
    )
    client = APIClient()
    client.force_authenticate(user)
    with override_settings(TIME_ZONE="America/New_York"):
        revisions = client.get(
            reverse("api:v2:project-revisions", kwargs={"id": commit.project_id})
        )
        projects = client.get(reverse("api:v2:projects"))
    assert revisions.status_code == status.HTTP_200_OK
    assert projects.status_code == status.HTTP_200_OK
    project = next(
        row for row in projects.json() if row["id"] == str(commit.project_id)
    )
    for data in (revisions.json()["commits"][0], project["latest_commit"]):
        assert data["id"] == commit.id
        assert data["authored_date"].endswith("Z")
        assert dt.datetime.fromisoformat(data["authored_date"]) == authored
        assert data["dt_since"] == "2 minutes ago"
