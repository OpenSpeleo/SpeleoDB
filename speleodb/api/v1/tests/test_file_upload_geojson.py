# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import pathlib
from typing import Any
from typing import cast

import pytest
from django.urls import reverse
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import ProjectType

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

    def _upload_files(
        self,
        *,
        fileformat: FileFormat,
        artifact_paths: list[pathlib.Path],
        commit_message: str,
    ) -> dict[str, Any]:
        with contextlib.ExitStack() as stack:
            opened_files = [
                stack.enter_context(path.open(mode="rb")) for path in artifact_paths
            ]
            response = self.client.put(
                reverse(
                    "api:v1:project-upload",
                    kwargs={
                        "id": self.project.id,
                        "fileformat": fileformat.label.lower(),
                    },
                ),
                {"artifact": opened_files, "message": commit_message},
                format="multipart",
                headers={"authorization": self.auth},
            )

        assert response.status_code == status.HTTP_200_OK, response.data
        return cast("dict[str, Any]", response.data["data"])

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

        assert ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=str(data["hexsha"]),
        ).exists()

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
        finally:
            self.project.release_mutex(self.user)

        assert ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=str(data["hexsha"]),
        ).exists()

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
