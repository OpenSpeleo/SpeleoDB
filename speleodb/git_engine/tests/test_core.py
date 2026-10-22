"""Exercise Git wrappers with deterministic local repository histories."""

from __future__ import annotations

from typing import TYPE_CHECKING

import git
import pytest

from speleodb.git_engine.core import GIT_COMMITTER
from speleodb.git_engine.core import GitRepo

if TYPE_CHECKING:
    from pathlib import Path


def test_initialization(tmp_path: Path) -> None:
    path = tmp_path / "new"
    repository = GitRepo.init(path)
    with repository:
        # Resolve both paths to handle macOS /var -> /private/var symlink
        assert repository.path.resolve() == path.resolve()
        with pytest.raises(ValueError):  # noqa: PT011
            _ = repository.head.commit


def test_clone_preserves_history_and_exposes_changed_blobs(tmp_path: Path) -> None:
    source_path = tmp_path / "source"
    with GitRepo.init(source_path) as source:
        survey = source_path / "survey.dat"
        survey.write_bytes(b"original survey")
        source.index.add(["survey.dat"])
        first = source.index.commit("Original survey", author=GIT_COMMITTER)
        survey.write_bytes(b"updated survey")
        source.index.add(["survey.dat"])
        latest = source.index.commit("Updated survey", author=GIT_COMMITTER)
        remote_path = tmp_path / "remote.git"
        with git.Repo.clone_from(source_path, remote_path, bare=True):
            cloned = GitRepo.clone_from(str(remote_path), tmp_path / "clone")
            with cloned:
                assert cloned.path == tmp_path / "clone"
                assert cloned.head.commit.hexsha == latest.hexsha
                assert [commit.hexsha for commit in cloned.iter_commits()] == [
                    latest.hexsha,
                    first.hexsha,
                ]
                changes = [
                    diff
                    for diff in cloned.head.commit.changes
                    if diff.change_type == "M"
                ]
                assert len(changes) == 1
                change = changes[0]
                assert change.a_path == change.b_path == "survey.dat"
                assert change.a_blob is not None
                assert change.b_blob is not None
                assert change.a_blob.data_stream.read() == b"original survey"
                assert change.b_blob.data_stream.read() == b"updated survey"
