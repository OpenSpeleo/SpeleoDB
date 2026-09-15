# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
import pathlib
import shutil
import uuid
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

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

if TYPE_CHECKING:
    from speleodb.git_engine.core import GitRepo


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

    def _seed_project(self, project: Project) -> str:
        repo: GitRepo = project.git_repo
        self.addCleanup(repo.close)
        assert repo.head.is_valid()
        return repo.head.commit.hexsha

    def _run_successfully(self, *arguments: str) -> None:
        # --all logs individual failures and continues. Merely returning or
        # deleting the local copy must never make a failed GitLab test pass.
        with self.assertLogs(Command.__module__, level="INFO") as logs:
            call_command("build_project_geojsons", *arguments)
        assert all(record.levelno < logging.ERROR for record in logs.records), (
            logs.output
        )

    @pytest.mark.skip_if_lighttest
    def test_all_mode_processes_only_eligible_project_type(self) -> None:
        compass_project: Project = ProjectFactory.create(
            type=ProjectType.COMPASS,
            exclude_geojson=False,
        )
        excluded: Project = ProjectFactory.create(
            type=ProjectType.COMPASS,
            exclude_geojson=True,
        )
        self._seed_project(self.project)
        self._seed_project(compass_project)
        self._seed_project(excluded)

        self._run_successfully("--all", "--project_type", ProjectType.COMPASS)

        assert not compass_project.git_repo_dir.exists()
        assert self.project.git_repo_dir.is_dir()
        assert excluded.git_repo_dir.is_dir()

    @pytest.mark.skip_if_lighttest
    def test_project_mode_processes_only_selected_project(self) -> None:
        other: Project = ProjectFactory.create(
            type=ProjectType.COMPASS, exclude_geojson=False
        )
        self._seed_project(self.project)
        other_sha: str = self._seed_project(other)

        self._run_successfully(
            "--project",
            str(self.project.id),
            "--fresh",
            "--force_recompute",
        )

        assert not self.project.git_repo_dir.exists()
        with other.git_repo as untouched:
            assert untouched.head.commit.hexsha == other_sha

    @pytest.mark.skip_if_lighttest
    def test_all_mode_continues_after_project_failure(self) -> None:
        self._seed_project(self.project)
        broken: Project = ProjectFactory.create(
            type=ProjectType.COMPASS, exclude_geojson=False
        )
        # A nonempty invalid working copy provokes an actual filesystem error;
        # GitRepo cannot replace it with a repository without losing local files.
        broken.git_repo_dir.mkdir(parents=True)
        (broken.git_repo_dir / "not-a-repository").touch()

        with self.assertLogs(Command.__module__, level="ERROR") as logs:
            call_command("build_project_geojsons", "--all")

        assert len(logs.records) == 1, logs.output
        assert str(broken.id) in logs.records[0].getMessage()
        assert logs.records[0].exc_info is not None
        assert isinstance(logs.records[0].exc_info[1], OSError)
        assert not broken.git_repo_dir.exists()
        assert not self.project.git_repo_dir.exists()

    def test_project_mode_raises_after_project_failure(self) -> None:
        self.project.git_repo_dir.mkdir(parents=True)
        (self.project.git_repo_dir / "not-a-repository").touch()

        with pytest.raises(CommandError, match="Unable to build GeoJSON") as raised:
            call_command("build_project_geojsons", "--project", str(self.project.id))

        assert isinstance(raised.value.__cause__, OSError)
        assert not self.project.git_repo_dir.exists()

    @pytest.mark.skip_if_lighttest
    def test_fresh_removes_existing_copy_before_clone_and_after_processing(
        self,
    ) -> None:
        initial_sha: str = self._seed_project(self.project)
        shutil.rmtree(self.project.git_repo_dir)
        command: Command = Command()
        for local_copy_exists in (False, True):
            with self.subTest(local_copy_exists=local_copy_exists):
                if local_copy_exists:
                    self.project.git_repo_dir.mkdir(parents=True)
                    (self.project.git_repo_dir / "stale-marker").touch()
                with self.assertLogs(Command.__module__, level="INFO") as logs:
                    command._process_project(  # noqa: SLF001
                        self.project,
                        force_recompute=False,
                        fresh=True,
                    )
                assert all(record.levelno < logging.ERROR for record in logs.records)
                assert not self.project.git_repo_dir.exists()
                # Actual remote history survives both fresh rebuilds.
                with self.project.git_repo as restored:
                    assert restored.head.commit.hexsha == initial_sha
                shutil.rmtree(self.project.git_repo_dir)

    def test_remove_local_copy_surfaces_unexpected_filesystem_failure(self) -> None:
        with (
            TemporaryDirectory() as directory,
            override_settings(DJANGO_GIT_PROJECTS_DIR=pathlib.Path(directory)),
        ):
            self.project.git_repo_dir.write_text("not a directory", encoding="utf-8")
            with pytest.raises(NotADirectoryError):
                Command._remove_local_copy(self.project)  # noqa: SLF001
            assert self.project.git_repo_dir.read_text() == "not a directory"

    def test_fresh_removal_failure_prevents_repository_access(self) -> None:
        with (
            TemporaryDirectory() as directory,
            override_settings(DJANGO_GIT_PROJECTS_DIR=pathlib.Path(directory)),
        ):
            self.project.git_repo_dir.write_text("not a directory", encoding="utf-8")
            with pytest.raises(NotADirectoryError):
                Command()._process_project(  # noqa: SLF001
                    self.project,
                    force_recompute=False,
                    fresh=True,
                )
            # Accessing Project.git_repo would unlink this file before retrying
            # provisioning. Its survival proves processing stopped at removal.
            assert self.project.git_repo_dir.read_text() == "not a directory"


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
