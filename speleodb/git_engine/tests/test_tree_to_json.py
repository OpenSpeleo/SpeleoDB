"""Serialize real Git trees without unrelated API uploads or remote provisioning."""

from __future__ import annotations

from typing import TYPE_CHECKING

from speleodb.git_engine.core import GIT_COMMITTER
from speleodb.git_engine.core import GitRepo

if TYPE_CHECKING:
    from pathlib import Path

EXECUTABLE_MODE = 0o755


def test_tree_to_json_preserves_nested_paths_modes_and_object_ids(
    tmp_path: Path,
) -> None:
    repository = GitRepo.init(tmp_path / "tree")
    with repository:
        files: dict[str, tuple[str, int]] = {
            "readme.txt": ("survey notes", 0o644),
            "nested/a survey.dat": ("survey measurements", 0o644),
            "nested/tools/export.sh": ("#!/bin/sh\nexit 0\n", EXECUTABLE_MODE),
        }
        for name, (contents, mode) in files.items():
            path = repository.path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
            path.chmod(mode)
        repository.index.add(list(files))
        repository.index.commit("Survey tree", author=GIT_COMMITTER)

        assert sorted(
            repository.head.commit.tree_to_json(), key=lambda row: row["path"]
        ) == [
            {
                "mode": "100755" if files[name][1] == EXECUTABLE_MODE else "100644",
                "type": "blob",
                "object": repository.index.entries[(name, 0)].hexsha,
                "path": name,
            }
            for name in sorted(files)
        ]


def test_tree_to_json_empty_initial_commit(tmp_path: Path) -> None:
    with GitRepo.init(tmp_path / "empty") as repository:
        repository.index.commit("Initial empty commit", author=GIT_COMMITTER)
        assert repository.head.commit.tree_to_json() == []
