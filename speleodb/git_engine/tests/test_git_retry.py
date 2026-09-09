# -*- coding: utf-8 -*-

from __future__ import annotations

import pathlib
import shutil
import tempfile
import traceback
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

ENCODED_CREDENTIAL = "fake%40credential"
DECODED_CREDENTIAL = "fake@credential"
REMOTE_URL = f"https://oauth2:{ENCODED_CREDENTIAL}@gitlab.example/test/project.git"
DECODED_REMOTE_URL = REMOTE_URL.replace(ENCODED_CREDENTIAL, DECODED_CREDENTIAL)


def remote_git_error(action: str) -> GitCommandError:
    return GitCommandError(
        ["git", action, REMOTE_URL],
        128,
        stderr=(
            f"fatal: unable to access '{REMOTE_URL}': remote unavailable; "
            f"decoded URL: {DECODED_REMOTE_URL}; credential: {DECODED_CREDENTIAL}"
        ),
    )


def assert_credentials_redacted(diagnostic_text: str) -> None:
    assert ENCODED_CREDENTIAL not in diagnostic_text
    assert DECODED_CREDENTIAL not in diagnostic_text
    assert "oauth2:" not in diagnostic_text
    assert "gitlab.example/test/project.git" in diagnostic_text
    assert "exit code(128)" in diagnostic_text
    assert "remote unavailable" in diagnostic_text


def assert_remote_backoff(mock_sleep: MagicMock) -> None:
    assert [mock_call.args[0] for mock_call in mock_sleep.call_args_list] == [
        1.0,
        2.0,
        4.0,
        8.0,
    ]


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
        self.repo.create_remote("origin", url=REMOTE_URL)

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
            patch.object(git.Git, "push", create=True, return_value=""),
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

    @patch("speleodb.utils.helpers.time.sleep")
    def test_push_retries_sanitized_transient_error(
        self, mock_sleep: MagicMock
    ) -> None:
        (self.git_path / "pushfile.txt").write_text("content")

        with (
            patch.object(
                git.Git,
                "push",
                create=True,
                side_effect=[remote_git_error("push"), ""],
            ) as mock_push,
            self.assertLogs("speleodb.utils.helpers", level="DEBUG") as logs,
        ):
            result = self.repo.commit_and_push_project(
                message="test",
                author_name="Test",
                author_email="test@test.com",
            )

        assert result is not None
        assert mock_push.call_count == 2  # noqa: PLR2004
        mock_sleep.assert_called_once_with(1.0)
        assert_credentials_redacted("\n".join(logs.output))

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

    @patch("speleodb.utils.helpers.time.sleep")
    def test_push_raises_redacted_error_after_exhausted_retries(
        self, mock_sleep: MagicMock
    ) -> None:
        """After DJANGO_GIT_RETRY_ATTEMPTS push failures, GitBaseError is raised."""
        (self.git_path / "pushfile.txt").write_text("content")

        with (
            patch.object(self.repo, "is_dirty", return_value=True),
            patch.object(
                git.Git,
                "push",
                create=True,
                side_effect=remote_git_error("push"),
            ) as mock_push,
            self.assertLogs("speleodb.utils.helpers", level="DEBUG") as logs,
            pytest.raises(GitBaseError, match="Impossible to push") as exc_info,
        ):
            self.repo.commit_and_push_project(
                message="test",
                author_name="Test",
                author_email="test@test.com",
            )

        traceback_text = "".join(
            traceback.format_exception(
                exc_info.type,
                exc_info.value,
                exc_info.tb,
            )
        )
        assert_credentials_redacted("\n".join([traceback_text, *logs.output]))
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None
        assert mock_push.call_count == 5  # noqa: PLR2004
        assert_remote_backoff(mock_sleep)


class PullAndFetchRetryTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.repo = GitRepo.init(path=pathlib.Path(self.tmpdir) / "test_repo")
        readme = self.repo.path / "README.md"
        readme.write_text("initial")
        self.repo.index.add([readme.name])
        self.repo.index.commit("initial commit")
        self.repo.create_remote("origin", url=REMOTE_URL)

    @patch("speleodb.utils.helpers.time.sleep")
    def test_pull_and_fetch_retry_sanitized_transient_errors(
        self, mock_sleep: MagicMock
    ) -> None:
        for operation_name in ("pull", "fetch"):
            with (
                self.subTest(operation=operation_name),
                patch.object(
                    git.Remote,
                    operation_name,
                    side_effect=[remote_git_error(operation_name), []],
                ) as remote_operation,
                self.assertLogs("speleodb.utils.helpers", level="DEBUG") as logs,
            ):
                mock_sleep.reset_mock()
                getattr(self.repo, operation_name)()

                assert remote_operation.call_count == 2  # noqa: PLR2004
                mock_sleep.assert_called_once_with(1.0)
                assert_credentials_redacted("\n".join(logs.output))

    @patch("speleodb.utils.helpers.time.sleep")
    def test_pull_and_fetch_raise_redacted_errors_after_exhaustion(
        self, mock_sleep: MagicMock
    ) -> None:
        for operation_name in ("pull", "fetch"):
            mock_sleep.reset_mock()
            with (
                self.subTest(operation=operation_name),
                patch.object(
                    git.Remote,
                    operation_name,
                    side_effect=remote_git_error(operation_name),
                ) as remote_operation,
                self.assertLogs("speleodb.utils.helpers", level="DEBUG") as logs,
                pytest.raises(
                    GitBaseError,
                    match=f"Impossible to {operation_name} repository",
                ) as exc_info,
            ):
                getattr(self.repo, operation_name)()

            traceback_text = "".join(
                traceback.format_exception(
                    exc_info.type,
                    exc_info.value,
                    exc_info.tb,
                )
            )
            assert_credentials_redacted("\n".join([traceback_text, *logs.output]))
            assert exc_info.value.__cause__ is None
            assert exc_info.value.__context__ is None
            assert remote_operation.call_count == 5  # noqa: PLR2004
            assert_remote_backoff(mock_sleep)

    @patch("speleodb.utils.helpers.time.sleep")
    def test_set_origin_url_raises_redacted_error_after_exhaustion(
        self, mock_sleep: MagicMock
    ) -> None:
        with (
            patch.object(
                git.Remote,
                "set_url",
                side_effect=remote_git_error("remote set-url"),
            ) as set_url,
            self.assertLogs("speleodb.utils.helpers", level="DEBUG") as logs,
            pytest.raises(
                GitBaseError,
                match="Impossible to configure origin for repository",
            ) as exc_info,
        ):
            self.repo.set_origin_url(REMOTE_URL)

        traceback_text = "".join(
            traceback.format_exception(
                exc_info.type,
                exc_info.value,
                exc_info.tb,
            )
        )
        assert_credentials_redacted("\n".join([traceback_text, *logs.output]))
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None
        assert set_url.call_count == 5  # noqa: PLR2004
        assert_remote_backoff(mock_sleep)


class CloneRetryTests(TestCase):
    @patch("speleodb.utils.helpers.time.sleep")
    def test_clone_retries_transient_git_command_errors(
        self, mock_sleep: MagicMock
    ) -> None:
        cloned_repo = MagicMock(spec=git.Repo)
        expected_repo = MagicMock(spec=GitRepo)
        transient_error = GitCommandError("clone", 128, stderr="not ready")

        with (
            patch.object(
                git.Repo,
                "clone_from",
                side_effect=[transient_error, cloned_repo],
            ) as mock_clone,
            patch.object(GitRepo, "from_repo", return_value=expected_repo),
        ):
            result = GitRepo.clone_from(
                url="https://gitlab.example/test/project.git",
                to_path=pathlib.Path("project"),
            )

        assert result is expected_repo
        assert mock_clone.call_count == 2  # noqa: PLR2004
        mock_sleep.assert_called_once_with(1.0)

    @patch("speleodb.utils.helpers.time.sleep")
    def test_clone_raises_git_base_error_after_retries(
        self, mock_sleep: MagicMock
    ) -> None:
        persistent_error = remote_git_error("clone")

        for use_keyword_url in (False, True):
            with self.subTest(use_keyword_url=use_keyword_url):
                project_path = pathlib.Path("project")
                clone_args = () if use_keyword_url else (REMOTE_URL, project_path)
                clone_kwargs = (
                    {"url": REMOTE_URL, "to_path": project_path}
                    if use_keyword_url
                    else {}
                )
                mock_sleep.reset_mock()
                with (
                    patch.object(
                        git.Repo,
                        "clone_from",
                        side_effect=persistent_error,
                    ) as mock_clone,
                    self.assertLogs("speleodb.utils.helpers", level="DEBUG") as logs,
                    pytest.raises(
                        GitBaseError, match="Impossible to clone repository"
                    ) as exc_info,
                ):
                    GitRepo.clone_from(*clone_args, **clone_kwargs)

                traceback_text = "".join(
                    traceback.format_exception(
                        exc_info.type,
                        exc_info.value,
                        exc_info.tb,
                    )
                )
                diagnostic_text = "\n".join([traceback_text, *logs.output])

                assert_credentials_redacted(diagnostic_text)
                assert exc_info.value.__cause__ is None
                assert exc_info.value.__context__ is None
                assert mock_clone.call_count == 5  # noqa: PLR2004
                assert_remote_backoff(mock_sleep)
