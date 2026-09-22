# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import pathlib
import re
from typing import Any
from typing import cast
from unittest.mock import patch

import orjson
import pytest
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import ProjectType
from speleodb.gis.geojson_generation import dispatch_pending_geojsons
from speleodb.gis.models import ProjectGeoJSON
from speleodb.gis.models import ProjectGeoJSONGeneration
from speleodb.gis.tasks import generate_project_geojson
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import Project
from speleodb.testing.gitlab_pool import get_pool

BASE_DIR = pathlib.Path(__file__).parent / "artifacts"
ARIANE_TEST_FILE = BASE_DIR / "test_simple.tml"
COMPASS_TEST_FILES = [
    BASE_DIR / "sample.mak",
    BASE_DIR / "sample-1.dat",
    BASE_DIR / "sample-2.dat",
]


@pytest.mark.skip_if_lighttest
class TestFileUploadGeoJSON(BaseAPIProjectTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )
        get_pool().prepare(self.project)

    def _upload_files(
        self,
        *,
        fileformat: FileFormat,
        artifact_paths: list[pathlib.Path],
        commit_message: str,
        expected_status: int = status.HTTP_200_OK,
    ) -> dict[str, Any]:
        with contextlib.ExitStack() as stack:
            converter = stack.enter_context(
                patch.object(
                    Project,
                    "build_geojson",
                    side_effect=AssertionError("Upload must not generate maps"),
                )
            )
            parser = stack.enter_context(
                patch(
                    "openspeleo_lib.interfaces.ArianeInterface.from_file",
                    side_effect=AssertionError("Upload must not parse surveys"),
                )
            )
            broker = stack.enter_context(
                patch(
                    "celery.current_app.send_task",
                    side_effect=AssertionError("Upload must not contact the broker"),
                )
            )
            opened_files = [
                stack.enter_context(path.open(mode="rb")) for path in artifact_paths
            ]
            response = self.client.put(
                reverse(
                    "api:v2:project-upload",
                    kwargs={
                        "id": self.project.id,
                        "fileformat": fileformat.label.lower(),
                    },
                ),
                {"artifact": opened_files, "message": commit_message},
                format="multipart",
                headers={"authorization": self.auth},
            )

        converter.assert_not_called()
        parser.assert_not_called()
        broker.assert_not_called()
        assert response.status_code == expected_status, response.content
        if expected_status == status.HTTP_304_NOT_MODIFIED:
            return {}
        return cast("dict[str, Any]", response.data)

    def _run_generation(self, commit_sha: str) -> None:
        assert not ProjectGeoJSON.objects.filter(commit_id=commit_sha).exists()
        generation = ProjectGeoJSONGeneration.objects.get(commit_id=commit_sha)
        assert generation.state == "pending"
        with patch("speleodb.gis.geojson_generation.current_app.send_task") as publish:
            dispatch_pending_geojsons()
        publish.assert_called_once()
        assert publish.call_args.kwargs["args"][0] == commit_sha
        generation.refresh_from_db()
        assert generation.state == "queued"
        generate_project_geojson.run(commit_sha, str(generation.token))

    def _assert_stored_shot_colors(self, commit_sha: str) -> None:
        artifact = ProjectGeoJSON.objects.get(commit_id=commit_sha)
        with artifact.file.open("rb") as source:
            data = orjson.loads(source.read())
        lines = [
            feature
            for feature in data["features"]
            if feature["geometry"]["type"] == "LineString"
        ]
        assert lines
        for feature in lines:
            color = feature["properties"]["color"]
            assert isinstance(color, str)
            assert re.fullmatch(r"#[0-9a-f]{6}|rgba\([0-9., ]+\)", color)
        response = self.client.get(
            reverse("api:v2:all-projects-geojson"),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK
        metadata = next(
            item for item in response.data if item["id"] == str(self.project.id)
        )
        assert metadata["geojson_file"]
        assert metadata["geojson_revision"] == artifact.geojson_revision
        assert metadata["geojson_commit_sha"] == commit_sha

    def test_upload_ariane_generates_geojson(self) -> None:
        self.project.type = ProjectType.ARIANE
        self.project.exclude_geojson = False
        self.project.save(update_fields=["type", "exclude_geojson"])

        self.project.acquire_mutex(self.user)
        try:
            data = self._upload_files(
                fileformat=FileFormat.ARIANE_TML,
                artifact_paths=[ARIANE_TEST_FILE],
                commit_message="Ariane upload with GeoJSON",
            )
        finally:
            self.project.release_mutex(self.user)

        self._run_generation(str(data["hexsha"]))
        assert ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=str(data["hexsha"]),
        ).exists()
        self._assert_stored_shot_colors(str(data["hexsha"]))

    def test_upload_ariane_skips_geojson_when_excluded(self) -> None:
        self.project.type = ProjectType.ARIANE
        self.project.exclude_geojson = True
        self.project.save(update_fields=["type", "exclude_geojson"])

        self.project.acquire_mutex(self.user)
        try:
            data = self._upload_files(
                fileformat=FileFormat.ARIANE_TML,
                artifact_paths=[ARIANE_TEST_FILE],
                commit_message="Ariane upload without GeoJSON",
            )
        finally:
            self.project.release_mutex(self.user)

        assert not ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=str(data["hexsha"]),
        ).exists()

        assert data["geojson_status"] == "skipped"
        assert not ProjectGeoJSONGeneration.objects.filter(
            commit_id=str(data["hexsha"])
        ).exists()

    def test_upload_auto_compass_generates_geojson(self) -> None:
        self.project.type = ProjectType.COMPASS
        self.project.exclude_geojson = False
        self.project.save(update_fields=["type", "exclude_geojson"])

        self.project.acquire_mutex(self.user)
        try:
            data = self._upload_files(
                fileformat=FileFormat.AUTO,
                artifact_paths=COMPASS_TEST_FILES,
                commit_message="Compass upload with GeoJSON",
            )
            self._run_generation(str(data["hexsha"]))
            artifact = ProjectGeoJSON.objects.get(commit_id=str(data["hexsha"]))
            original_revision = artifact.geojson_revision
            self._assert_stored_shot_colors(str(data["hexsha"]))
            self._upload_files(
                fileformat=FileFormat.AUTO,
                artifact_paths=COMPASS_TEST_FILES,
                commit_message="Identical Compass source",
                expected_status=status.HTTP_304_NOT_MODIFIED,
            )
            assert (
                ProjectGeoJSONGeneration.objects.filter(
                    commit__project=self.project
                ).count()
                == 1
            )
            artifact.refresh_from_db()
            assert artifact.geojson_revision == original_revision
        finally:
            self.project.release_mutex(self.user)

        assert ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=str(data["hexsha"]),
        ).exists()
        self._assert_stored_shot_colors(str(data["hexsha"]))

    def test_upload_auto_compass_skips_geojson_when_excluded(self) -> None:
        self.project.type = ProjectType.COMPASS
        self.project.exclude_geojson = True
        self.project.save(update_fields=["type", "exclude_geojson"])

        self.project.acquire_mutex(self.user)
        try:
            data = self._upload_files(
                fileformat=FileFormat.AUTO,
                artifact_paths=COMPASS_TEST_FILES,
                commit_message="Compass upload without GeoJSON",
            )
        finally:
            self.project.release_mutex(self.user)

        assert not ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=str(data["hexsha"]),
        ).exists()

        assert data["geojson_status"] == "skipped"
        assert not ProjectGeoJSONGeneration.objects.filter(
            commit_id=str(data["hexsha"])
        ).exists()

    def test_upload_auto_compass_incomplete_bundle_skips_geojson(self) -> None:
        self.project.type = ProjectType.COMPASS
        self.project.exclude_geojson = False
        self.project.save(update_fields=["type", "exclude_geojson"])

        self.project.acquire_mutex(self.user)
        try:
            data = self._upload_files(
                fileformat=FileFormat.AUTO,
                artifact_paths=[BASE_DIR / "sample-1.dat"],
                commit_message="Compass upload missing MAK",
            )
        finally:
            self.project.release_mutex(self.user)

        assert not ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=str(data["hexsha"]),
        ).exists()

        self._run_generation(str(data["hexsha"]))
        generation = ProjectGeoJSONGeneration.objects.get(commit_id=str(data["hexsha"]))
        assert generation.state == "skipped"
