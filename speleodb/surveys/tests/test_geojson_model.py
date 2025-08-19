from __future__ import annotations

import json
from typing import Any

import boto3
import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from speleodb.api.v1.tests.test_project_geojson_api import sha1_hash
from speleodb.surveys.models import GeoJSON
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

        obj = GeoJSON(
            project=project,
            commit_sha=commit_sha1,
            commit_date=timezone.now(),
            file=upload,
        )
        obj.save()

        assert obj.file.name == f"{project.id}/{commit_sha1}.json"

    def test_invalid_geojson_rejected(self, project: Project) -> None:
        payload = {"type": "NotFeatureCollection"}
        upload = make_uploaded("map.geojson", payload)

        obj = GeoJSON(
            project=project,
            commit_sha=sha1_hash(),
            commit_date=timezone.now(),
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

        obj = GeoJSON(
            project=project,
            commit_sha=sha1_hash(),
            commit_date=timezone.now(),
            file=upload,
        )
        obj.save()

        with pytest.raises(ValidationError):
            obj.save()

    def test_signed_url_generation(
        self, settings: Any, project: Project, monkeypatch: Any
    ) -> None:
        payload = {"type": "FeatureCollection", "features": []}
        upload = make_uploaded("map.geojson", payload)

        obj = GeoJSON(
            project=project,
            commit_sha=sha1_hash(),
            commit_date=timezone.now(),
            file=upload,
        )
        obj.save()

        # Stub boto3 client
        client = boto3.client(
            "s3", region_name=getattr(settings, "AWS_S3_REGION_NAME", "us-east-1")
        )

        # generate_presigned_url is local method; instead patch boto3.client to return
        # our client
        def fake_client(*args: Any, **kwargs: Any) -> Any:
            return client

        monkeypatch.setattr("boto3.client", fake_client)

        url = obj.get_signed_download_url()

        assert isinstance(url, str)
        assert len(url) > 0
