"""Status remains separate from upload success and identifies the rendered source."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from typing import Any

import pytest
from django.core.files.storage import FileSystemStorage
from django.db.models import QuerySet
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import ProjectGeoJSON
from speleodb.gis.models import ProjectGeoJSONGeneration
from speleodb.gis.project_geojson_services import replace_project_geojson
from speleodb.surveys.models import ProjectCommit

if TYPE_CHECKING:
    from pathlib import Path

    from speleodb.surveys.models import Project
    from speleodb.users.models import User


POINT = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [1, 2]},
            "properties": {},
        }
    ],
}


@pytest.fixture
def reader(user: User, project: Project) -> APIClient:
    UserProjectPermissionFactory(
        target=user, project=project, level=PermissionLevel.READ_ONLY
    )
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def source(project: Project) -> ProjectCommit:
    return ProjectCommit.objects.create(
        pk="a" * 40,
        project=project,
        author_name="Surveyor",
        author_email="surveyor@example.org",
        authored_date=timezone.now(),
        message="Source upload",
    )


@pytest.fixture
def local_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ProjectGeoJSON._meta.get_field("file"),  # noqa: SLF001
        "storage",
        FileSystemStorage(location=tmp_path),
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state", ["pending", "queued", "running", "ready", "skipped", "failed"]
)
def test_status_states(reader: APIClient, source: ProjectCommit, state: str) -> None:
    ProjectGeoJSONGeneration.objects.create(
        commit=source,
        state=state,
        last_error_code="invalid_coordinates" if state == "failed" else "",
        last_error="Station <A>: longitude -183 must be >= -180"
        if state == "failed"
        else "",
    )
    response = reader.get(
        reverse("api:v2:project-geojson-status", kwargs={"id": source.project_id})
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["state"] == state
    assert response.data["source_commit_sha"] == source.pk
    assert response.data["geojson_commit_sha"] is None
    assert response.data["geojson_revision"] is None
    assert response.data["updated_at"]
    if state == "failed":
        assert "Station <A>" in response.data["error"]
        assert response.data["error_code"] == "invalid_coordinates"


@pytest.mark.django_db
def test_no_generation_record_and_excluded_status(
    reader: APIClient, source: ProjectCommit
) -> None:
    url = reverse("api:v2:project-geojson-status", kwargs={"id": source.project_id})
    assert reader.get(url).data["state"] == "not_requested"
    source.project.exclude_geojson = True
    source.project.save(update_fields=["exclude_geojson"])
    assert reader.get(url).data["state"] == "skipped"


@pytest.mark.django_db
def test_empty_project(reader: APIClient, project: Project) -> None:
    response = reader.get(
        reverse("api:v2:project-geojson-status", kwargs={"id": project.pk})
    )
    assert response.data["state"] == "not_requested"
    assert response.data["source_commit_sha"] is None


@pytest.mark.django_db
def test_old_artifact_survives_failure_then_revision_changes(
    reader: APIClient, source: ProjectCommit, local_artifacts: None
) -> None:
    previous = replace_project_geojson(source.project, source, POINT)
    new = ProjectCommit.objects.create(
        pk="b" * 40,
        project=source.project,
        author_name=source.author_name,
        author_email=source.author_email,
        authored_date=source.authored_date + timedelta(seconds=1),
        message="Invalid source",
    )
    generation = ProjectGeoJSONGeneration.objects.create(
        commit=new, state="failed", last_error="Invalid coordinates"
    )
    url = reverse("api:v2:project-geojson-status", kwargs={"id": source.project_id})
    failed = reader.get(url).data
    assert failed["state"] == "failed"
    assert failed["source_commit_sha"] == new.pk
    assert failed["geojson_commit_sha"] == source.pk
    assert failed["geojson_revision"] == previous.geojson_revision
    replacement = replace_project_geojson(source.project, new, POINT)
    generation.state = "ready"
    generation.last_error = ""
    generation.save()
    ready = reader.get(url).data
    assert ready["source_commit_sha"] == failed["source_commit_sha"]
    assert ready["state"] == "ready"
    assert ready["geojson_commit_sha"] == new.pk
    assert ready["geojson_revision"] == replacement.geojson_revision
    assert ready["geojson_revision"] != failed["geojson_revision"]


@pytest.mark.django_db
def test_out_of_order_completion_with_equal_authored_dates(
    reader: APIClient, source: ProjectCommit, local_artifacts: None
) -> None:
    newer = ProjectCommit.objects.create(
        pk="0" * 40,
        project=source.project,
        author_name=source.author_name,
        author_email=source.author_email,
        authored_date=source.authored_date,
        message="Later source with same Git timestamp",
    )
    ProjectCommit.objects.filter(pk=source.pk).update(
        creation_date=timezone.now() - timedelta(seconds=1)
    )
    newest_artifact = replace_project_geojson(source.project, newer, POINT)
    replace_project_geojson(source.project, source, POINT)
    response = reader.get(
        reverse("api:v2:project-geojson-status", kwargs={"id": source.project_id})
    )
    assert response.data["source_commit_sha"] == newer.pk
    assert response.data["geojson_commit_sha"] == newer.pk
    assert response.data["geojson_revision"] == newest_artifact.geojson_revision
    assert response.data["state"] == "ready"


@pytest.mark.django_db
def test_unrelated_upload_does_not_hide_pending_survey(
    reader: APIClient, source: ProjectCommit
) -> None:
    ProjectGeoJSONGeneration.objects.create(commit=source, state="pending")
    later = ProjectCommit.objects.create(
        pk="b" * 40,
        project=source.project,
        author_name=source.author_name,
        author_email=source.author_email,
        authored_date=source.authored_date + timedelta(seconds=1),
        message="Attach a photograph",
    )
    response = reader.get(
        reverse("api:v2:project-geojson-status", kwargs={"id": source.project_id})
    )
    assert response.data["state"] == "pending"
    assert response.data["source_commit_sha"] == later.pk
    assert response.data["generation_commit_sha"] == source.pk


@pytest.mark.django_db
def test_publication_between_status_reads_cannot_freeze_stale_artifact(
    reader: APIClient,
    source: ProjectCommit,
    local_artifacts: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ProjectGeoJSONGeneration.objects.create(commit=source, state="running")
    original_first = QuerySet.first
    published = False

    def publish_between_reads(queryset: QuerySet[Any]) -> Any:
        nonlocal published
        result = original_first(queryset)
        if not published and queryset.model in {
            ProjectGeoJSONGeneration,
            ProjectGeoJSON,
        }:
            published = True
            replace_project_geojson(source.project, source, POINT)
            ProjectGeoJSONGeneration.objects.filter(commit=source).update(state="ready")
        return result

    monkeypatch.setattr(QuerySet, "first", publish_between_reads)
    url = reverse("api:v2:project-geojson-status", kwargs={"id": source.project_id})
    concurrent = reader.get(url).data
    assert published
    assert concurrent["geojson_commit_sha"] == source.pk
    assert concurrent["state"] in {"running", "ready"}
    settled = reader.get(url).data
    assert settled["state"] == "ready"
    assert settled["geojson_commit_sha"] == source.pk


@pytest.mark.django_db
@pytest.mark.parametrize("level", [None, PermissionLevel.WEB_VIEWER])
def test_status_requires_source_read_permission(
    user: User, project: Project, level: PermissionLevel | None
) -> None:
    if level is not None:
        UserProjectPermissionFactory(target=user, project=project, level=level)
    client = APIClient()
    url = reverse("api:v2:project-geojson-status", kwargs={"id": project.pk})
    assert client.get(url).status_code in {
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    }
    client.force_authenticate(user)
    assert client.get(url).status_code == status.HTTP_403_FORBIDDEN
