"""Project metadata must not add a query for every map project."""

from __future__ import annotations

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import Format
from speleodb.surveys.models import ProjectCommit
from speleodb.surveys.models import ProjectMutex


class TestGeoJsonProjectQueries(BaseAPITestCase):
    def test_metadata_queries_remain_bounded(self) -> None:
        counts: list[int] = []
        expected: dict[str, str | None] = {}
        expected_commits: dict[str, str | None] = {}
        for index in range(3):
            project = ProjectFactory.create(created_by=self.user.email)
            UserProjectPermissionFactory.create(
                target=self.user, project=project, level=PermissionLevel.READ_ONLY
            )
            Format.objects.create(project=project, _format=FileFormat.COMPASS_ZIP)
            expected_commits[str(project.pk)] = None
            if index != 1:
                commit = ProjectCommit.objects.create(
                    id=f"{index + 1:040x}",
                    project=project,
                    author_name="Author",
                    author_email=self.user.email,
                    authored_date=timezone.now(),
                    message="Survey revision",
                )
                expected_commits[str(project.pk)] = commit.id
            ProjectMutex.objects.create(
                project=project, user=self.user, is_active=index != 1
            )
            expected[str(project.pk)] = self.user.email if index != 1 else None
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(
                    reverse("api:v2:all-projects-geojson"),
                    headers={"authorization": self.auth},
                )
            assert response.status_code == status.HTTP_200_OK
            assert {row["id"] for row in response.data} == set(expected)
            for row in response.data:
                expected_commit = expected_commits[row["id"]]
                assert row["commit_count"] == (1 if expected_commit else 0)
                if expected_commit is None:
                    assert row["latest_commit"] is None
                else:
                    assert row["latest_commit"]["id"] == expected_commit
                    assert {
                        item["name"] for item in row["latest_commit"]["formats"]
                    } == {FileFormat.COMPASS_ZIP.webname, "Everything (ZIP)"}
                assert row["geojson_file"] is None
                assert row["geojson_revision"] is None
                assert row["geojson_commit_sha"] is None
                assert "permission" not in row
                mutex = row["active_mutex"]
                assert (mutex["user"] if mutex else None) == expected[row["id"]]
            counts.append(len(queries))
        assert counts == [counts[0]] * len(counts)
