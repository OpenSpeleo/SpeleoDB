# -*- coding: utf-8 -*-

from __future__ import annotations

import pathlib
import shutil
import tempfile
import types
import unittest
from unittest import TestCase

import git
import pytest

from speleodb.git_engine.core import GitRepo


class NewRepoTest(TestCase):
    def test_initialization(self) -> None:
        with tempfile.TemporaryDirectory() as _dir:
            git_path = pathlib.Path(_dir) / "torch"

            repo = GitRepo.init(path=git_path)

            # Resolve both paths to handle macOS /var -> /private/var symlink
            assert repo.path.resolve() == git_path.resolve()

            with pytest.raises(ValueError):  # noqa: PT011
                _ = repo.head.commit


class CloneRepoTest(TestCase):
    def setUp(self) -> None:
        self.git_dir = tempfile.TemporaryDirectory(delete=False)

        self.git_path = pathlib.Path(self.git_dir.name) / "wheel"

        self.repo = GitRepo.clone_from(
            url="https://github.com/pypa/wheel.git",
            to_path=self.git_path,
            branch="main",
        )

        return super().setUp()

    def tearDown(self) -> None:
        shutil.rmtree(self.git_dir.name)
        return super().tearDown()

    def test_clone(self) -> None:
        assert self.repo.path == self.git_path

        hexsha = self.repo.head.commit.hexsha
        assert isinstance(hexsha, str)
        assert hexsha != ""

    def test_read_changes(self) -> None:
        changes = self.repo.head.commit.changes
        assert isinstance(changes, types.GeneratorType)

        for diff in changes:
            assert isinstance(diff, git.Diff), type(diff)


if __name__ == "__main__":
    unittest.main()
