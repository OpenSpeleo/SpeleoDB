# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
import pathlib
import re
import shutil
import uuid
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from typing import Any
from typing import cast
from unittest.mock import patch

import orjson
import pytest
from celery.exceptions import SoftTimeLimitExceeded
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
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import Project
from speleodb.surveys.tasks import refresh_all_projects_geojson
from speleodb.testing.gitlab_pool import canonical_project
from speleodb.testing.gitlab_pool import get_pool

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
        self.project = canonical_project(
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

    def test_force_recompute_flag_accepts_both_spellings(self) -> None:
        parser = Command().create_parser("manage.py", "build_project_geojsons")
        for flag in ("--force_recompute", "--force-recompute"):
            options = parser.parse_args(["--all", flag])
            assert options.all_projects is True
            assert options.force_recompute is True

    def test_task_stops_when_gitlab_wraps_initialization_timeout(self) -> None:
        with (
            patch.object(GitlabManager, "_gl", None),
            patch.object(
                GitlabManager, "_initialize", side_effect=SoftTimeLimitExceeded
            ),
        ):
            result = refresh_all_projects_geojson.apply(throw=False)
        assert result.failed()
        assert isinstance(result.result, SoftTimeLimitExceeded)
        assert not self.project.git_repo_dir.exists()

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
        get_pool().prepare(project)
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
        compass_project: Project = canonical_project(
            PermissionLevel.READ_AND_WRITE,
            type=ProjectType.COMPASS,
            exclude_geojson=False,
        )
        excluded: Project = canonical_project(
            PermissionLevel.READ_ONLY,
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
        other: Project = canonical_project(
            PermissionLevel.READ_AND_WRITE,
            type=ProjectType.COMPASS,
            exclude_geojson=False,
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
        get_pool().prepare(self.project)

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
        initial_revision = initial_geojson.geojson_revision

        call_command("build_project_geojsons", *command_args)
        skipped_creation_date = ProjectGeoJSON.objects.get(
            project=self.project,
            commit__id=hexsha,
        ).creation_date
        assert skipped_creation_date == initial_creation_date

        with self.assertLogs(Command.__module__, level="INFO") as logs:
            result = refresh_all_projects_geojson.apply(throw=True)
        assert result.successful()
        assert all(record.levelno < logging.ERROR for record in logs.records)
        regenerated = ProjectGeoJSON.objects.get(
            project=self.project,
            commit__id=hexsha,
        )
        assert regenerated.creation_date > initial_creation_date
        assert regenerated.geojson_revision != initial_revision
        with regenerated.file.open("rb") as source:
            lines = [
                feature
                for feature in orjson.loads(source.read())["features"]
                if feature["geometry"]["type"] == "LineString"
            ]
        assert lines
        assert all("color" in feature["properties"] for feature in lines)

        # A forced rebuild with no matching source must keep the usable artifact.
        self.project.type = ProjectType.COMPASS
        self.project.save(update_fields=["type"])
        call_command("build_project_geojsons", *command_args, "--force-recompute")
        retained = ProjectGeoJSON.objects.get(commit_id=hexsha)
        assert retained.geojson_revision == regenerated.geojson_revision
        assert retained.file.name is not None
        assert retained.file.storage.exists(retained.file.name)

    def test_command_builds_and_recomputes_geojson_for_compass_project(self) -> None:
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

        artifact = ProjectGeoJSON.objects.get(project=self.project, commit_id=hexsha)
        original_revision = artifact.geojson_revision
        with artifact.file.open("rb") as source:
            original_data = orjson.loads(source.read())
        command_args = ("--project", str(self.project.id))
        call_command("build_project_geojsons", *command_args)
        artifact.refresh_from_db()
        assert artifact.geojson_revision == original_revision

        with self.assertLogs(Command.__module__, level="INFO") as logs:
            result = refresh_all_projects_geojson.apply(throw=True)
        assert result.successful()
        assert all(record.levelno < logging.ERROR for record in logs.records)
        artifact.refresh_from_db()
        assert artifact.geojson_revision != original_revision
        with artifact.file.open("rb") as source:
            regenerated_data = orjson.loads(source.read())
        for data in [original_data, regenerated_data]:
            lines = [
                feature
                for feature in data["features"]
                if feature["geometry"]["type"] == "LineString"
            ]
            assert lines
            assert all(
                re.fullmatch(r"#[0-9a-f]{6}", feature["properties"]["color"])
                for feature in lines
            )
            for feature in data["features"]:
                feature["properties"].pop("color", None)
        # Random coloring may change; every other exported value must stay exact.
        assert regenerated_data == original_data

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

        result = refresh_all_projects_geojson.apply(throw=True)
        assert result.successful()

        assert not ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=hexsha,
        ).exists()

    def test_task_timeout_stops_rebuild_and_cleans_checkout(self) -> None:
        self.project.type = ProjectType.ARIANE
        self.project.exclude_geojson = True
        self.project.save(update_fields=["type", "exclude_geojson"])
        self.project.acquire_mutex(self.user)
        try:
            hexsha = self._upload_files(
                fileformat=FileFormat.ARIANE_TML,
                artifact_paths=[ARIANE_TEST_FILE],
                commit_message="Ariane upload for task timeout",
            )
        finally:
            self.project.release_mutex(self.user)
        self.project.exclude_geojson = False
        self.project.save(update_fields=["exclude_geojson"])

        # The worker can interrupt either materialization or conversion. Both
        # must escape the command's commit/project error-isolation handlers.
        for target in (
            f"{Command.__module__}.Command._materialize_geojson_source",
            "speleodb.surveys.models.project.survey_to_geojson",
        ):
            with (
                self.subTest(target=target),
                patch(target, side_effect=SoftTimeLimitExceeded),
            ):
                result = refresh_all_projects_geojson.apply(throw=False)
            assert result.failed()
            assert isinstance(result.result, SoftTimeLimitExceeded)
            assert not self.project.git_repo_dir.exists()
            assert not ProjectGeoJSON.objects.filter(commit_id=hexsha).exists()
