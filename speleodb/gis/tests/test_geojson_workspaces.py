"""Exercise real filesystem cleanup, process death and bounded Git streaming."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tracemalloc
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone
from git import Actor

from speleodb.common.enums import ProjectType
from speleodb.gis.geojson_sources import materialize_geojson_source
from speleodb.gis.geojson_workspaces import cleanup_geojson_workspaces
from speleodb.gis.geojson_workspaces import geojson_workspace
from speleodb.git_engine.core import GitRepo
from speleodb.surveys.models import Project

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings


@pytest.mark.parametrize("error_type", [ValueError, SoftTimeLimitExceeded])
def test_workspace_cleans_all_files_after_failure(
    settings: Settings, tmp_path: Path, error_type: type[Exception]
) -> None:
    settings.GEOJSON_GENERATION_SCRATCH_DIR = str(tmp_path / "scratch")
    reached_failure = False

    def fail_inside_workspace() -> None:
        nonlocal reached_failure
        with geojson_workspace(prefix="rebuild-") as directory:
            for name in ("repository", "sources", "git-auth", "output"):
                child = directory / name
                child.mkdir()
                (child / "private-data").write_text("task-owned")
            reached_failure = True
            raise error_type

    with pytest.raises(error_type):
        fail_inside_workspace()
    assert reached_failure
    assert not list(Path(settings.GEOJSON_GENERATION_SCRATCH_DIR).iterdir())


def test_workspace_cleans_success_and_preserves_unrelated_files(
    settings: Settings, tmp_path: Path
) -> None:
    settings.GEOJSON_GENERATION_SCRATCH_DIR = str(tmp_path / "scratch")
    root = Path(settings.GEOJSON_GENERATION_SCRATCH_DIR)
    root.mkdir()
    unrelated = root / "operator-file"
    unrelated.write_text("preserve")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private-data").write_text("preserve")
    link = root / "work-symlink"
    link.symlink_to(outside, target_is_directory=True)
    with geojson_workspace(prefix="rebuild-") as directory:
        assert directory.parent == root
        assert stat.S_IMODE(directory.stat().st_mode) == stat.S_IRWXU
        (directory / "temporary").write_text("remove")
    cleanup_geojson_workspaces()
    assert not directory.exists()
    assert unrelated.read_text() == "preserve"
    assert link.is_symlink()
    assert (outside / "private-data").read_text() == "preserve"


def test_live_workspace_survives_sweep_then_is_reclaimed_after_sigkill(
    settings: Settings, tmp_path: Path
) -> None:
    root = tmp_path / "scratch"
    settings.GEOJSON_GENERATION_SCRATCH_DIR = str(root)
    # A disposable child is necessary: killing pytest cannot verify recovery.
    # A separate process holds the real kernel lock. SIGKILL cannot execute
    # TemporaryDirectory cleanup; the next sweep must reclaim all its files.
    script = """
import sys
from django.conf import settings
settings.configure(GEOJSON_GENERATION_SCRATCH_DIR=sys.argv[1],
                   GEOJSON_GENERATION_CLEANUP_GRACE_SECONDS=300)
from speleodb.gis.geojson_workspaces import geojson_workspace
with geojson_workspace(prefix="rebuild-") as directory:
    for name in ("repository", "sources", "git-auth", "output"):
        child = directory / name
        child.mkdir()
        (child / "private-data").write_text("task-owned")
    print(directory, flush=True)
    sys.stdin.read()
"""
    # Fixed interpreter/script with only a pytest-owned directory as an argument.
    with subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", script, str(root)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as process:
        try:
            assert process.stdout is not None
            line = process.stdout.readline().strip()
            assert line, process.communicate(timeout=10)[1]
            directory = Path(line)
            old = timezone.now().timestamp() - 3600
            os.utime(directory, (old, old))
            cleanup_geojson_workspaces()
            assert (directory / "repository" / "private-data").is_file()
        finally:
            process.kill()
            process.communicate(timeout=10)
    cleanup_geojson_workspaces()
    assert not directory.exists()
    assert not list(root.iterdir())


def test_sweep_recovers_process_death_before_lock_creation(
    settings: Settings, tmp_path: Path
) -> None:
    settings.GEOJSON_GENERATION_SCRATCH_DIR = str(tmp_path)
    directory = tmp_path / "work-rebuild-interrupted"
    directory.mkdir()
    old = timezone.now().timestamp() - 3600
    os.utime(directory, (old, old))
    cleanup_geojson_workspaces()
    assert not directory.exists()


def test_ariane_materialization_streams_large_blob_at_exact_revision(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    with closing(GitRepo.init(source)) as repository:
        original = source / "ariane.tml"
        block = b"survey-data\n" * 8192
        with original.open("wb") as output:
            for _ in range(128):
                output.write(block)
        repository.index.add(["ariane.tml"])
        actor = Actor("Surveyor", "surveyor@example.test")
        commit = repository.index.commit(
            "Large immutable source", author=actor, committer=actor
        )
        original.write_text("changed after commit")
        destination = tmp_path / "materialized"
        destination.mkdir()
        tracemalloc.start()
        try:
            result = materialize_geojson_source(
                Project(type=ProjectType.ARIANE),
                repository.commit(commit.hexsha),
                destination,
            )
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert result == destination / "ariane.tml"
        assert result.stat().st_size == len(block) * 128
        # GitPython copies 512 KiB chunks. A full BytesIO/blob copy would exceed
        # this bound by several times for the source above.
        assert peak < 3 * 1024 * 1024
        with result.open("rb") as output:
            for _ in range(128):
                assert output.read(len(block)) == block
