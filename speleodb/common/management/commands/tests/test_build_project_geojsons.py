# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import pathlib
import uuid
from tempfile import TemporaryDirectory
from typing import Any
from typing import cast
from unittest.mock import MagicMock
from unittest.mock import PropertyMock
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import ProjectType
from speleodb.common.management.commands.build_project_geojsons import Command
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import Project

BASE_DIR = (
    pathlib.Path(__file__).parent.parent.parent.parent.parent
    / "api"
    / "v2"
    / "tests"
    / "artifacts"
)
ARIANE_TEST_FILE = BASE_DIR / "test_simple.tml"
COMPASS_TEST_FILES = [
    BASE_DIR / "sample.mak",
    BASE_DIR / "sample-1.dat",
    BASE_DIR / "sample-2.dat",
]


class TestBuildProjectGeoJSONCommand(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.project = ProjectFactory.create(
            type=ProjectType.ARIANE,
            exclude_geojson=False,
        )

    def test_command_requires_exactly_one_selection_mode(self) -> None:
        with pytest.raises(CommandError):
            call_command("build_project_geojsons")

        with pytest.raises(CommandError):
            call_command(
                "build_project_geojsons",
                "--all",
                "--project",
                str(self.project.id),
            )

    def test_command_rejects_invalid_project_uuid(self) -> None:
        with pytest.raises(CommandError):
            call_command("build_project_geojsons", "--project", "not-a-uuid")

    def test_command_rejects_unknown_project(self) -> None:
        missing_project_id = uuid.uuid4()

        with pytest.raises(CommandError, match="does not exist"):
            call_command(
                "build_project_geojsons",
                "--project",
                str(missing_project_id),
            )

    def test_command_rejects_excluded_project(self) -> None:
        self.project.exclude_geojson = True
        self.project.save(update_fields=["exclude_geojson"])

        with pytest.raises(CommandError, match="excluded"):
            call_command(
                "build_project_geojsons",
                "--project",
                str(self.project.id),
            )

    def test_command_rejects_fresh_in_all_mode(self) -> None:
        with pytest.raises(CommandError, match="--fresh"):
            call_command("build_project_geojsons", "--all", "--fresh")

    def test_command_rejects_project_type_in_project_mode(self) -> None:
        with pytest.raises(CommandError, match="--project_type"):
            call_command(
                "build_project_geojsons",
                "--project",
                str(self.project.id),
                "--project_type",
                ProjectType.ARIANE,
            )

    @patch.object(Command, "_process_project")
    def test_all_mode_processes_only_eligible_project_type(
        self, mock_process_project: MagicMock
    ) -> None:
        compass_project = ProjectFactory.create(
            type=ProjectType.COMPASS,
            exclude_geojson=False,
        )
        _ = ProjectFactory.create(
            type=ProjectType.COMPASS,
            exclude_geojson=True,
        )

        call_command(
            "build_project_geojsons",
            "--all",
            "--project_type",
            ProjectType.COMPASS,
        )

        mock_process_project.assert_called_once_with(
            compass_project,
            force_recompute=False,
        )

    @patch.object(Command, "_process_project")
    def test_project_mode_processes_only_selected_project(
        self, mock_process_project: MagicMock
    ) -> None:
        _ = ProjectFactory.create(type=ProjectType.COMPASS, exclude_geojson=False)

        call_command(
            "build_project_geojsons",
            "--project",
            str(self.project.id),
            "--fresh",
            "--force_recompute",
        )

        mock_process_project.assert_called_once_with(
            self.project,
            force_recompute=True,
            fresh=True,
        )

    @patch.object(Command, "_process_project")
    def test_all_mode_continues_after_project_failure(
        self, mock_process_project: MagicMock
    ) -> None:
        _ = ProjectFactory.create(type=ProjectType.COMPASS, exclude_geojson=False)
        mock_process_project.side_effect = [RuntimeError("broken project"), None]

        call_command("build_project_geojsons", "--all")

        assert mock_process_project.call_count == 2  # noqa: PLR2004

    @patch.object(Command, "_process_project", side_effect=RuntimeError("clone failed"))
    def test_project_mode_raises_after_project_failure(
        self, mock_process_project: MagicMock
    ) -> None:
        with pytest.raises(CommandError, match="Unable to build GeoJSON"):
            call_command(
                "build_project_geojsons",
                "--project",
                str(self.project.id),
            )

        mock_process_project.assert_called_once()

    def test_fresh_removes_existing_copy_before_clone_and_after_processing(
        self,
    ) -> None:
        command = Command()

        for local_copy_exists in (False, True):
            with (
                self.subTest(local_copy_exists=local_copy_exists),
                TemporaryDirectory() as tmp_dir,
            ):
                git_projects_dir = pathlib.Path(tmp_dir)
                with override_settings(DJANGO_GIT_PROJECTS_DIR=git_projects_dir):
                    git_repo_dir = self.project.git_repo_dir
                    if local_copy_exists:
                        git_repo_dir.mkdir(parents=True)
                        (git_repo_dir / "stale-marker").touch()

                    git_repo = MagicMock()
                    git_repo.commits = []

                    def clone_project(
                        repo_dir: pathlib.Path = git_repo_dir,
                        repo: MagicMock = git_repo,
                    ) -> MagicMock:
                        assert not repo_dir.exists()
                        repo_dir.mkdir(parents=True)
                        (repo_dir / "fresh-marker").touch()
                        return repo

                    with patch.object(
                        Project,
                        "git_repo",
                        new_callable=PropertyMock,
                        side_effect=clone_project,
                    ) as mock_git_repo:
                        command._process_project(  # noqa: SLF001
                            self.project,
                            force_recompute=False,
                            fresh=True,
                        )

                    mock_git_repo.assert_called_once_with()
                    assert not git_repo_dir.exists()

    def test_remove_local_copy_surfaces_unexpected_failure(self) -> None:
        with (
            patch(
                "speleodb.common.management.commands.build_project_geojsons.shutil.rmtree",
                side_effect=PermissionError("permission denied"),
            ),
            pytest.raises(PermissionError, match="permission denied"),
        ):
            Command._remove_local_copy(self.project)  # noqa: SLF001

    def test_fresh_removal_failure_prevents_repository_access(self) -> None:
        command = Command()

        with (
            patch.object(
                command,
                "_remove_local_copy",
                side_effect=PermissionError("permission denied"),
            ),
            patch.object(
                Project,
                "git_repo",
                new_callable=PropertyMock,
            ) as mock_git_repo,
            pytest.raises(PermissionError, match="permission denied"),
        ):
            command._process_project(  # noqa: SLF001
                self.project,
                force_recompute=False,
                fresh=True,
            )

        mock_git_repo.assert_not_called()


@pytest.mark.skip_if_lighttest
class TestBuildProjectGeoJSONs(BaseAPIProjectTestCase):
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

        assert response.status_code == status.HTTP_200_OK, response.data
        response_data = cast("dict[str, Any]", response.data)
        return cast("str", response_data["hexsha"])

    def test_command_builds_and_recomputes_geojson_for_ariane_project(self) -> None:
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
        command_args = ("--project", str(self.project.id))
        call_command("build_project_geojsons", *command_args)

        initial_geojson = ProjectGeoJSON.objects.get(
            project=self.project,
            commit__id=hexsha,
        )
        initial_creation_date = initial_geojson.creation_date

        call_command("build_project_geojsons", *command_args)
        skipped_creation_date = ProjectGeoJSON.objects.get(
            project=self.project,
            commit__id=hexsha,
        ).creation_date
        assert skipped_creation_date == initial_creation_date

        call_command(
            "build_project_geojsons",
            *command_args,
            "--force_recompute",
        )
        recomputed_creation_date = ProjectGeoJSON.objects.get(
            project=self.project,
            commit__id=hexsha,
        ).creation_date
        assert recomputed_creation_date > initial_creation_date

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
        call_command("build_project_geojsons", "--all")

        assert ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=hexsha,
        ).exists()

    def test_all_mode_skips_projects_excluded_from_geojson(self) -> None:
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

        call_command("build_project_geojsons", "--all")

        assert not ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=hexsha,
        ).exists()
