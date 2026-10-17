# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
import os
import pathlib
import re
import signal
import threading
import uuid
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

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
from speleodb.api.v2.tests.factories import ProjectCommitFactory
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.background_jobs.archive_sources import ArchiveBuildError
from speleodb.background_jobs.archive_sources import GitCloneUnavailableError
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import ProjectType
from speleodb.common.management.commands.build_project_geojsons import Command
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import Project
from speleodb.surveys.tasks import refresh_all_projects_geojson
from speleodb.surveys.tasks import refresh_project_geojson
from speleodb.testing.gitlab_pool import canonical_project
from speleodb.testing.gitlab_pool import get_pool

if TYPE_CHECKING:
    from types import FrameType

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
        self.scratch = pathlib.Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(
            override_settings(GEOJSON_GENERATION_SCRATCH_DIR=str(self.scratch))
        )

    def test_command_requires_exactly_one_selection_mode(self) -> None:
        with pytest.raises(CommandError):
            call_command("build_project_geojsons")

        with pytest.raises(CommandError):
            call_command(
                "build_project_geojsons", "--all", "--project", str(self.project.id)
            )

    def test_command_rejects_invalid_project_uuid(self) -> None:
        with pytest.raises(CommandError):
            call_command("build_project_geojsons", "--project", "not-a-uuid")

    def test_command_rejects_unknown_project(self) -> None:
        missing_project_id = uuid.uuid4()
        with pytest.raises(CommandError, match="does not exist"):
            call_command("build_project_geojsons", "--project", str(missing_project_id))

    def test_force_recompute_flag_accepts_both_spellings(self) -> None:
        parser = Command().create_parser("manage.py", "build_project_geojsons")
        for flag in ("--force_recompute", "--force-recompute"):
            options = parser.parse_args(["--all", flag])
            assert options.all_projects is True
            assert options.force_recompute is True

    def test_command_rejects_excluded_project(self) -> None:
        self.project.exclude_geojson = True
        self.project.save(update_fields=["exclude_geojson"])
        with pytest.raises(CommandError, match="excluded"):
            call_command("build_project_geojsons", "--project", str(self.project.id))
        assert not list(self.scratch.iterdir())

    def test_command_rejects_obsolete_checkout_option(self) -> None:
        with pytest.raises(CommandError, match="unrecognized arguments"):
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
        # deleting the temporary copy must never make a failed GitLab test pass.
        with self.assertLogs(Command.__module__, level="INFO") as logs:
            call_command("build_project_geojsons", *arguments)
        assert all(record.levelno < logging.ERROR for record in logs.records), (
            logs.output
        )
        assert not list(self.scratch.iterdir())

    @pytest.mark.skip_if_lighttest
    def test_all_mode_processes_only_eligible_project_type(self) -> None:
        compass_project: Project = canonical_project(
            PermissionLevel.READ_AND_WRITE,
            type=ProjectType.COMPASS,
            exclude_geojson=False,
        )
        excluded: Project = canonical_project(
            PermissionLevel.READ_ONLY, type=ProjectType.COMPASS, exclude_geojson=True
        )
        self._seed_project(self.project)
        self._seed_project(compass_project)
        self._seed_project(excluded)
        with self.assertLogs(Command.__module__, level="INFO") as logs:
            call_command(
                "build_project_geojsons", "--all", "--project_type", ProjectType.COMPASS
            )
        messages = "\n".join(logs.output)
        assert str(compass_project.id) in messages
        assert str(self.project.id) not in messages
        assert str(excluded.id) not in messages
        assert all(record.levelno < logging.ERROR for record in logs.records)
        assert compass_project.git_repo_dir.is_dir()
        assert self.project.git_repo_dir.is_dir()
        assert excluded.git_repo_dir.is_dir()
        assert not list(self.scratch.iterdir())

    @pytest.mark.skip_if_lighttest
    def test_project_mode_preserves_shared_checkout_and_untracked_files(self) -> None:
        original_sha: str = self._seed_project(self.project)
        marker = self.project.git_repo_dir / "uncommitted-upload"
        marker.write_text("retain upload work", encoding="utf-8")
        self._run_successfully("--project", str(self.project.id), "--force_recompute")
        assert marker.read_text() == "retain upload work"
        with self.project.git_repo as untouched:
            assert untouched.head.commit.hexsha == original_sha
        marker.unlink()

    @pytest.mark.skip_if_lighttest
    def test_all_mode_continues_after_project_failure(self) -> None:
        self._seed_project(self.project)
        broken: Project = ProjectFactory.create(
            type=ProjectType.COMPASS, exclude_geojson=False
        )
        ProjectCommitFactory.create(project=broken)
        # The remote is genuinely absent despite recorded history; read-only
        # rebuilds must fail rather than provision a replacement repository.
        with self.assertLogs(Command.__module__, level="INFO") as logs:
            call_command("build_project_geojsons", "--all")
        errors = [record for record in logs.records if record.levelno >= logging.ERROR]
        assert len(errors) == 1, logs.output
        assert str(broken.id) in errors[0].getMessage()
        assert errors[0].exc_info is not None
        assert isinstance(errors[0].exc_info[1], GitCloneUnavailableError)
        assert any(
            str(self.project.id) in record.getMessage() for record in logs.records
        )
        assert self.project.git_repo_dir.is_dir()
        assert not list(self.scratch.iterdir())

    def test_project_failure_preserves_shared_files(self) -> None:
        self.project.git_repo_dir.mkdir(parents=True)
        marker = self.project.git_repo_dir / "not-a-repository"
        marker.touch()
        with (
            override_settings(GITLAB_HOST_URL="invalid/host"),
            pytest.raises(CommandError, match="Unable to build GeoJSON") as raised,
        ):
            call_command("build_project_geojsons", "--project", str(self.project.id))
        assert isinstance(raised.value.__cause__, ArchiveBuildError)
        assert marker.exists()
        assert not list(self.scratch.iterdir())


@pytest.mark.skip_if_lighttest
class TestBuildProjectGeoJSONs(BaseAPIProjectTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )
        get_pool().prepare(self.project)
        self.scratch = pathlib.Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(
            override_settings(GEOJSON_GENERATION_SCRATCH_DIR=str(self.scratch))
        )

    def tearDown(self) -> None:
        assert not list(self.scratch.iterdir())
        super().tearDown()

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
            result = refresh_project_geojson.apply(
                args=(str(self.project.id),),
                kwargs={"force_recompute": True},
                throw=True,
            )
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
            result = refresh_project_geojson.apply(
                args=(str(self.project.id),),
                kwargs={"force_recompute": True},
                throw=True,
            )
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
        assert result.result == {"enqueued": 0, "tasks": []}

        assert not ProjectGeoJSON.objects.filter(
            project=self.project,
            commit__id=hexsha,
        ).exists()

    def test_task_timeout_stops_clone_and_cleans_all_temporary_files(self) -> None:
        self.project.exclude_geojson = False
        self.project.save(update_fields=["exclude_geojson"])
        self.project.git_repo_dir.mkdir(parents=True, exist_ok=True)
        shared_marker = self.project.git_repo_dir / "unfinished-upload"
        shared_marker.write_text("preserve", encoding="utf-8")
        stopped = threading.Event()
        interrupted = threading.Event()

        def interrupt_clone() -> None:
            while not stopped.wait(0.001):
                if any(self.scratch.glob("*/repository")):
                    interrupted.set()
                    os.kill(os.getpid(), signal.SIGUSR1)
                    return

        def soft_timeout(_signum: int, _frame: FrameType | None) -> None:
            raise SoftTimeLimitExceeded

        previous = signal.signal(signal.SIGUSR1, soft_timeout)
        watcher = threading.Thread(target=interrupt_clone)
        watcher.start()
        try:
            result = refresh_project_geojson.apply(
                args=(str(self.project.id),),
                kwargs={"force_recompute": True},
                throw=False,
            )
        finally:
            stopped.set()
            watcher.join(timeout=5)
            signal.signal(signal.SIGUSR1, previous)
        assert not watcher.is_alive()
        assert interrupted.is_set()
        assert result.failed()
        assert isinstance(result.result, SoftTimeLimitExceeded)
        assert not list(self.scratch.iterdir())
        assert shared_marker.read_text() == "preserve"
        shared_marker.unlink()
