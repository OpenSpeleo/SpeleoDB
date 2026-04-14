# -*- coding: utf-8 -*-

from __future__ import annotations

import pathlib
import shutil
import tempfile
from typing import TYPE_CHECKING
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import PropertyMock
from unittest.mock import patch

import git
import pytest
from git.exc import GitCommandError

from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.exceptions import GitBaseError

if TYPE_CHECKING:
    from git import Commit
    from git.index.typ import BaseIndexEntry


class CommitAndPushRetryTests(TestCase):
    """Tests for retry logic on index.add, index.commit, and push."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.git_path = pathlib.Path(self.tmpdir) / "test_repo"
        self.repo = GitRepo.init(path=self.git_path)

        # Create an initial commit so HEAD exists
        readme = self.git_path / "README.md"
        readme.write_text("initial")
        self.repo.index.add(["README.md"])
        self.repo.index.commit("initial commit")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("speleodb.utils.helpers.time.sleep")
    def test_index_add_retries_on_git_command_error(
        self, mock_sleep: MagicMock
    ) -> None:
        """index.add should retry on GitCommandError (e.g. index.lock)."""
        real_add = git.IndexFile.add
        call_count = 0

        def flaky_add(
            self_idx: git.IndexFile,
            items: str,
        ) -> list[BaseIndexEntry]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise GitCommandError("add", "index.lock exists")
            return real_add(self_idx, items)

        with (
            patch.object(git.IndexFile, "add", flaky_add),
            patch.object(self.repo, "is_dirty", return_value=False),
        ):
            result = self.repo.commit_and_push_project(
                message="test",
                author_name="Test",
                author_email="test@test.com",
            )

        assert call_count == 2  # noqa: PLR2004
        assert result is None
        mock_sleep.assert_called_once()

    @patch("speleodb.utils.helpers.time.sleep")
    def test_index_commit_retries_on_git_command_error(
        self, mock_sleep: MagicMock
    ) -> None:
        """index.commit should retry on GitCommandError."""
        (self.git_path / "newfile.txt").write_text("content")

        real_commit = git.IndexFile.commit
        call_count = 0

        def flaky_commit(
            self_idx: git.IndexFile,
            message: str,
            *,
            author: git.Actor | None = None,
            committer: git.Actor | None = None,
        ) -> Commit:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise GitCommandError("commit", "index.lock exists")
            return real_commit(self_idx, message, author=author, committer=committer)

        with (
            patch.object(git.IndexFile, "commit", flaky_commit),
            patch.object(self.repo, "is_dirty", return_value=True),
            patch.object(git.Git, "execute", return_value=""),
            patch(
                "speleodb.git_engine.core.GitRepo.active_branch",
                new_callable=PropertyMock,
                return_value=MagicMock(name="master"),
            ),
        ):
            result = self.repo.commit_and_push_project(
                message="test",
                author_name="Test",
                author_email="test@test.com",
            )

        assert call_count == 2  # noqa: PLR2004
        assert result is not None
        mock_sleep.assert_called_once()

    def test_index_add_raises_after_exhausted_retries(self) -> None:
        """After DJANGO_GIT_RETRY_ATTEMPTS failures, the error should propagate."""

        def always_fail(self_idx: git.IndexFile, items: str) -> list[BaseIndexEntry]:
            raise GitCommandError("add", "persistent lock")

        with (
            patch.object(git.IndexFile, "add", always_fail),
            patch("speleodb.utils.helpers.time.sleep"),
            pytest.raises(GitCommandError),
        ):
            self.repo.commit_and_push_project(
                message="test",
                author_name="Test",
                author_email="test@test.com",
            )

    def test_index_commit_raises_after_exhausted_retries(self) -> None:
        """After DJANGO_GIT_RETRY_ATTEMPTS failures on commit, error propagates."""

        def always_fail(
            self_idx: git.IndexFile,
            message: str,
            *,
            author: git.Actor | None = None,
            committer: git.Actor | None = None,
        ) -> Commit:
            raise GitCommandError("commit", "persistent lock")

        with (
            patch.object(self.repo, "is_dirty", return_value=True),
            patch.object(git.IndexFile, "commit", always_fail),
            patch("speleodb.utils.helpers.time.sleep"),
            pytest.raises(GitCommandError),
        ):
            self.repo.commit_and_push_project(
                message="test",
                author_name="Test",
                author_email="test@test.com",
            )

    def test_push_raises_after_exhausted_retries(self) -> None:
        """After DJANGO_GIT_RETRY_ATTEMPTS push failures, GitBaseError is raised."""
        (self.git_path / "pushfile.txt").write_text("content")

        def always_fail_push(self_git: git.Git, command: str, **kwargs: object) -> str:
            raise GitCommandError("push", "remote error")

        mock_origin = MagicMock()
        mock_origin.url = "https://token@gitlab.com/test/repo.git"
        mock_remotes = MagicMock()
        mock_remotes.origin = mock_origin

        with (
            patch.object(self.repo, "is_dirty", return_value=True),
            patch.object(git.Git, "execute", always_fail_push),
            patch(
                "speleodb.git_engine.core.GitRepo.active_branch",
                new_callable=PropertyMock,
                return_value=MagicMock(name="master"),
            ),
            patch.object(
                type(self.repo),
                "remotes",
                new_callable=PropertyMock,
                return_value=mock_remotes,
            ),
            patch("speleodb.utils.helpers.time.sleep"),
            pytest.raises(GitBaseError, match="Impossible to push"),
        ):
            self.repo.commit_and_push_project(
                message="test",
                author_name="Test",
                author_email="test@test.com",
            )
