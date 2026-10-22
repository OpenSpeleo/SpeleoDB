"""Exercise real filesystem cleanup, process death and bounded Git streaming."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone
from git import Actor
from gitdb.base import OStream

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


def test_ariane_materialization_streams_blob_at_exact_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    with closing(GitRepo.init(source)) as repository:
        original = source / "ariane.tml"
        contents = b"survey-data\n" * 8
        original.write_bytes(contents)
        repository.index.add(["ariane.tml"])
        actor = Actor("Surveyor", "surveyor@example.test")
        commit = repository.index.commit(
            "Immutable source", author=actor, committer=actor
        )
        original.write_text("changed after commit")
        destination = tmp_path / "materialized"
        destination.mkdir()
        committed = repository.commit(commit.hexsha)
        source_sha = (committed.tree / "ariane.tml").binsha
        original_stream = repository.odb.stream
        read_sizes: list[int] = []

        class BoundedReader:
            def __init__(self, stream: Any) -> None:
                self.stream = stream

            def read(self, size: int = -1) -> bytes:
                # Reject whole-blob reads without allocating a large blob or
                # measuring process memory; retain the real Git stream contract.
                assert 0 < size <= 512 * 1024
                read_sizes.append(size)
                return self.stream.read(size)  # type: ignore[no-any-return]

        def guarded_stream(binsha: bytes) -> Any:
            stream = original_stream(binsha)
            if binsha == source_sha:
                return OStream(
                    stream.binsha,
                    stream.type,
                    stream.size,
                    BoundedReader(stream.stream),
                )
            return stream

        monkeypatch.setattr(repository.odb, "stream", guarded_stream)
        result = materialize_geojson_source(
            Project(type=ProjectType.ARIANE), committed, destination
        )
        assert result == destination / "ariane.tml"
        assert result.read_bytes() == contents
        assert read_sizes
