"""Sequential contracts for explicit project reset, cloning and storage deletion."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from unittest.mock import patch

import git
import pytest
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.base import ContentFile
from django.test import override_settings

from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.background_jobs.archive_sources import GitCloneUnavailableError
from speleodb.background_jobs.archive_sources import GitSource
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.utils.s3_storages import GeoJSONStorage

if TYPE_CHECKING:
    from collections.abc import Generator

    from speleodb.surveys.models import Project


@pytest.fixture
def local_history(tmp_path: Path) -> Generator[tuple[Project, Path, list[str]]]:
    with override_settings(DJANGO_GIT_PROJECTS_DIR=tmp_path / "checkouts"):
        project = ProjectFactory.create(exclude_geojson=True)
        remote = tmp_path / "remote.git"
        actor = git.Actor("Operations test", "operations@example.test")
        seed = GitRepo.init(tmp_path / "seed")
        seed.git.symbolic_ref("HEAD", f"refs/heads/{settings.DJANGO_GIT_BRANCH_NAME}")
        with (
            git.Repo.init(
                remote, bare=True, initial_branch=settings.DJANGO_GIT_BRANCH_NAME
            ) as upstream,
            seed,
        ):
            seed.create_remote("origin", str(remote))
            initial = seed.index.commit(
                "Initial history", author=actor, committer=actor
            )
            (seed.path / "survey.txt").write_text("Small revision", encoding="utf-8")
            seed.index.add(["survey.txt"])
            latest = seed.index.commit("Survey revision", author=actor, committer=actor)
            seed.git.push("origin", settings.DJANGO_GIT_BRANCH_NAME)
            hashes = [initial.hexsha, latest.hexsha]
            assert upstream.head.commit.hexsha == latest.hexsha
            # Substitute only remote configuration; cloning, Git history and
            # storage remain real application operations.
            with (
                patch.object(
                    GitlabCredentials, "project_url", return_value=str(remote)
                ),
                patch(
                    "speleodb.surveys.models.project.project_git_source",
                    return_value=GitSource(url=str(remote), token="", project_id=None),
                ),
                patch(
                    "speleodb.surveys.models.project.GitlabManager.create_or_clone_project",
                    side_effect=lambda selected: GitRepo.clone_from(
                        str(remote), selected.git_repo_dir
                    ),
                ),
            ):
                yield project, remote, hashes


@pytest.mark.django_db
def test_checkout_deletion_rejects_symlinks_and_preserves_neighboring_files(
    tmp_path: Path,
) -> None:
    with override_settings(DJANGO_GIT_PROJECTS_DIR=tmp_path / "checkouts"):
        project = ProjectFactory.create()
        root = Path(settings.DJANGO_GIT_PROJECTS_DIR)
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        sentinel = outside / "keep"
        sentinel.write_text("keep", encoding="utf-8")
        (root / str(project.pk)).symlink_to(outside, target_is_directory=True)
        with pytest.raises(RuntimeError, match="unsafe"):
            project.discard_checkout()
        assert sentinel.read_text() == "keep"
        (root / str(project.pk)).unlink()
        owned = root / str(project.pk)
        owned.mkdir()
        (owned / "keep").write_text("keep", encoding="utf-8")
        project.discard_checkout()
        assert not owned.exists()
        assert sentinel.read_text() == "keep"


@pytest.mark.django_db
def test_reset_reconstructs_initial_history_purges_all_artifacts_and_preserves_remote(
    local_history: tuple[Project, Path, list[str]],
) -> None:
    project, remote, hashes = local_history
    storage = GeoJSONStorage()
    neighbor = ProjectFactory.create()
    names = [f"{project.pk}/{kind}.json" for kind in ("current", "retired", "orphan")]
    neighbor_name = f"{neighbor.pk}/keep.json"
    saved: list[str] = []
    try:
        for name in [*names, neighbor_name]:
            # Keep each completed upload for cleanup if a later upload fails.
            saved.append(  # noqa: PERF401 - Retain partial uploads for cleanup.
                storage.save(
                    name, ContentFile(b'{"type":"FeatureCollection","features":[]}')
                )
            )
        repository = project.git_repo
        project.construct_git_history_from_project(repository)
        (repository.path / "stale").write_text("stale", encoding="utf-8")
        stages: list[str] = []
        summary: dict[str, Any] = project.reset_git_history(progress=stages.append)
        assert summary["commits"] == len(hashes)
        assert summary["deleted_objects"] == len(names)
        assert summary["geojson_skipped"] is True
        assert set(project.commits.values_list("id", flat=True)) == set(hashes)
        assert not (project.git_repo_dir / "stale").exists()
        assert not any(storage.exists(name) for name in names)
        assert storage.exists(neighbor_name)
        with git.Repo(remote) as upstream:
            assert upstream.head.commit.hexsha == hashes[-1]
            assert set(upstream.references) == {upstream.head.reference}
        assert stages[-1] == "history_rebuilt"
        repository = project.git_repo
        assert repository.remotes.origin.url == str(remote)
        project.checkout_commit_or_reset_default_branch()
        assert repository.head.commit.hexsha == hashes[-1]
        # A manual rerun starts from zero and reconstructs the same remote again.
        again = project.reset_git_history()
        assert again["deleted_objects"] == 0
        assert set(project.commits.values_list("id", flat=True)) == set(hashes)
    finally:
        for name in saved:
            storage.delete(name)


@pytest.mark.django_db
def test_reset_failure_leaves_manual_rerun_starting_from_zero(
    local_history: tuple[Project, Path, list[str]],
) -> None:
    project, _remote, hashes = local_history
    repository = project.git_repo
    project.construct_git_history_from_project(repository)
    # A nonexistent bucket exercises the real purge failure. The failure must
    # escape; a new explicit execution reconstructs history with valid storage.
    with (
        override_settings(
            AWS_STORAGE_BUCKET_NAME=f"missing-reset-test-{uuid.uuid4().hex}"
        ),
        pytest.raises(ClientError) as raised,
    ):
        project.reset_git_history()
    assert raised.value.response["Error"]["Code"] == "NoSuchBucket"
    project.refresh_from_db()
    assert not project.commits.exists()
    summary = project.reset_git_history()
    assert summary["commits"] == len(hashes)
    assert set(project.commits.values_list("id", flat=True)) == set(hashes)


@pytest.mark.django_db
def test_reset_validates_remote_before_deleting_history(
    local_history: tuple[Project, Path, list[str]], tmp_path: Path
) -> None:
    project, _remote, hashes = local_history
    repository = project.git_repo
    project.construct_git_history_from_project(repository)
    with (
        patch(
            "speleodb.surveys.models.project.project_git_source",
            return_value=GitSource(url=str(tmp_path / "missing.git"), token=""),
        ),
        pytest.raises(GitCloneUnavailableError, match="not found"),
    ):
        project.reset_git_history()
    project.refresh_from_db()
    assert set(project.commits.values_list("id", flat=True)) == set(hashes)


@pytest.mark.django_db
def test_reset_rejects_invalid_remote_head_before_deleting_history_or_objects(
    local_history: tuple[Project, Path, list[str]],
) -> None:
    project, remote, hashes = local_history
    repository = project.git_repo
    project.construct_git_history_from_project(repository)
    (repository.path / "keep-local").write_text("unchanged", encoding="utf-8")
    with git.Repo(remote) as upstream:
        upstream.git.symbolic_ref("HEAD", "refs/heads/missing-default")
        assert not upstream.head.is_valid()
    storage = GeoJSONStorage()
    payload = b'{"type":"FeatureCollection","features":[]}'
    key = storage.save(f"{project.pk}/keep-map.json", ContentFile(payload))
    try:
        with pytest.raises(RuntimeError, match="no default-branch history"):
            project.reset_git_history()
        project.refresh_from_db()
        assert set(project.commits.values_list("id", flat=True)) == set(hashes)
        assert (project.git_repo_dir / "keep-local").read_text() == "unchanged"
        with storage.open(key, "rb") as saved:
            assert saved.read() == payload
    finally:
        storage.delete(key)


@pytest.mark.django_db
def test_reset_installs_checkout_when_worker_checkout_root_does_not_exist(
    local_history: tuple[Project, Path, list[str]],
) -> None:
    project, _remote, hashes = local_history
    assert not Path(settings.DJANGO_GIT_PROJECTS_DIR).exists()
    summary = project.reset_git_history()
    assert summary["commits"] == len(hashes)
    repository = project.git_repo
    assert repository.head.commit.hexsha == hashes[-1]
    assert set(project.commits.values_list("id", flat=True)) == set(hashes)
