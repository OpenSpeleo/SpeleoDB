# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import pathlib
from typing import Any
from typing import cast

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import ProjectType
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import FileFormat

BASE_DIR = (
    pathlib.Path(__file__).parent.parent.parent.parent.parent
    / "api"
    / "v1"
    / "tests"
    / "artifacts"
)
ARIANE_TEST_FILE = BASE_DIR / "test_simple.tml"
COMPASS_TEST_FILES = [
    BASE_DIR / "sample.mak",
    BASE_DIR / "sample-1.dat",
    BASE_DIR / "sample-2.dat",
]


@pytest.mark.skip_if_lighttest
class TestBuildAllProjectGeoJSONs(BaseAPIProjectTestCase):
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
    ) -> str:
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
        response_data = cast("dict[str, Any]", response.data["data"])
        return cast("str", response_data["hexsha"])

    def test_command_builds_geojson_for_ariane_project(self) -> None:
        self.project.type = ProjectType.ARIANE
        self.project.exclude_geojson = True
        self.project.save(update_fields=["type", "exclude_geojson"])

        self.project.acquire_mutex(self.user)
        try:
            hexsha = self._upload_files(
                fileformat=FileFormat.ARIANE_TML,
                artifact_paths=[ARIANE_TEST_FILE],
                commit_message="Ariane upload for command generation",
            )
        finally:
            self.project.release_mutex(self.user)

        assert not ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=hexsha,
        ).exists()

        self.project.exclude_geojson = False
        self.project.save(update_fields=["exclude_geojson"])
        call_command("build_all_project_geojsons")

        assert ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=hexsha,
        ).exists()

    def test_command_builds_geojson_for_compass_project(self) -> None:
        self.project.type = ProjectType.COMPASS
        self.project.exclude_geojson = True
        self.project.save(update_fields=["type", "exclude_geojson"])

        self.project.acquire_mutex(self.user)
        try:
            hexsha = self._upload_files(
                fileformat=FileFormat.AUTO,
                artifact_paths=COMPASS_TEST_FILES,
                commit_message="Compass upload for command generation",
            )
        finally:
            self.project.release_mutex(self.user)

        assert not ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=hexsha,
        ).exists()

        self.project.exclude_geojson = False
        self.project.save(update_fields=["exclude_geojson"])
        call_command("build_all_project_geojsons")

        assert ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=hexsha,
        ).exists()

    def test_command_skips_projects_excluded_from_geojson(self) -> None:
        self.project.type = ProjectType.COMPASS
        self.project.exclude_geojson = True
        self.project.save(update_fields=["type", "exclude_geojson"])

        self.project.acquire_mutex(self.user)
        try:
            hexsha = self._upload_files(
                fileformat=FileFormat.AUTO,
                artifact_paths=COMPASS_TEST_FILES,
                commit_message="Compass excluded from command generation",
            )
        finally:
            self.project.release_mutex(self.user)

        call_command("build_all_project_geojsons")

        assert not ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=hexsha,
        ).exists()
