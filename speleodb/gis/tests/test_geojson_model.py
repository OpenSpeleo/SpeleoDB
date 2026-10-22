from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any
from uuid import UUID

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from speleodb.api.v2.tests.test_project_geojson_commits_api import sha1_hash
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import ProjectCommit

if TYPE_CHECKING:
    from speleodb.surveys.models import Project


def make_uploaded(name: str, payload: dict[str, Any]) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name=name,
        content=json.dumps(payload).encode("utf-8"),
        content_type="application/geo+json",
    )


@pytest.mark.django_db
class TestGeoJSONModel:
    def test_valid_creation_and_path(self, project: Project) -> None:
        payload = {"type": "FeatureCollection", "features": []}
        upload = make_uploaded("map.geojson", payload)

        commit_sha1 = sha1_hash()
        commit = ProjectCommit.objects.create(
            id=commit_sha1,
            project=project,
            author_name="John Doe",
            author_email="john.doe@example.com",
            authored_date=timezone.now(),
            message="Initial commit",
        )

        obj = ProjectGeoJSON(
            commit=commit,
            project=project,
            file=upload,
        )
        obj.save()

        assert obj.file.name is not None
        directory, filename = obj.file.name.split("/")
        assert directory == str(project.id)
        assert filename.endswith(".json")
        assert UUID(filename.removesuffix(".json")).version == 4  # noqa: PLR2004

    def test_invalid_geojson_rejected(self, project: Project) -> None:
        payload = {"type": "NotFeatureCollection"}
        upload = make_uploaded("map.geojson", payload)

        commit_sha = sha1_hash()
        commit = ProjectCommit.objects.create(
            id=commit_sha,
            project=project,
            author_name="John Doe",
            author_email="john.doe@example.com",
            authored_date=timezone.now(),
            message="Initial commit",
        )

        obj = ProjectGeoJSON(
            commit=commit,
            project=project,
            file=upload,
        )

        with pytest.raises(
            ValidationError,
            match="The file uploaded does not appear to be a valid GeoJSON",
        ):
            obj.save()

    def test_immutable_after_create(self, project: Project) -> None:
        payload = {"type": "FeatureCollection", "features": []}
        upload = make_uploaded("map.geojson", payload)

        commit_sha = sha1_hash()
        commit = ProjectCommit.objects.create(
            id=commit_sha,
            project=project,
            author_name="John Doe",
            author_email="john.doe@example.com",
            authored_date=timezone.now(),
            message="Initial commit",
        )

        obj = ProjectGeoJSON(
            commit=commit,
            project=project,
            file=upload,
        )
        obj.save()

        with pytest.raises(ValidationError):
            obj.save()
