# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import pathlib
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import traceback
from io import BytesIO
from typing import TYPE_CHECKING
from typing import Any
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import PropertyMock
from unittest.mock import patch

import git
import pytest
from django.test import override_settings
from git.exc import GitCommandError

from speleodb.git_engine.core import GIT_COMMITTER
from speleodb.git_engine.core import GitCommit
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.exceptions import GitBaseError
from speleodb.git_engine.operations import BoundedGit

if TYPE_CHECKING:
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
    """Tests for retry logic on index.add, supervised commit, and push."""

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
    def test_commit_retries_on_git_command_error(self, mock_sleep: MagicMock) -> None:
        """The supervised commit should retry on GitCommandError."""
        (self.git_path / "newfile.txt").write_text("content")

        real_commit = GitRepo._commit_project  # noqa: SLF001
        call_count = 0

        def flaky_commit(
            repo: GitRepo,
            message: str,
            *,
            author: git.Actor,
        ) -> GitCommit:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise GitCommandError("commit", "index.lock exists")
            return real_commit(repo, message, author=author)

        with (
            patch.object(GitRepo, "_commit_project", flaky_commit),
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

    def test_commit_raises_after_exhausted_retries(self) -> None:
        """After DJANGO_GIT_RETRY_ATTEMPTS failures on commit, error propagates."""

        def always_fail(
            repo: GitRepo,
            message: str,
            *,
            author: git.Actor,
        ) -> GitCommit:
            raise GitCommandError("commit", "persistent lock")

        with (
            patch.object(self.repo, "is_dirty", return_value=True),
            patch.object(GitRepo, "_commit_project", always_fail),
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

    def test_supervised_commit_preserves_author_and_committer(self) -> None:
        commit = self.repo._commit_project(  # noqa: SLF001
            "authored commit",
            author=git.Actor("Original Author", "author@example.org"),
        )

        assert commit.message == "authored commit"
        assert commit.author.name == "Original Author"
        assert commit.author.email == "author@example.org"
        assert commit.committer == GIT_COMMITTER

    @override_settings(DJANGO_GIT_COMMAND_TIMEOUT_SECONDS=0.5)
    @patch("speleodb.utils.helpers.time.sleep")
    def test_post_commit_timeout_does_not_retry_completed_commit(
        self, sleep: MagicMock
    ) -> None:
        hook: pathlib.Path = pathlib.Path(self.repo.git_dir) / "hooks" / "post-commit"
        hook.write_text(
            f"#!/bin/sh\nexec {shlex.quote(sys.executable)} -c "
            "'import signal; signal.pause()'\n"
        )
        hook.chmod(0o755)
        original_head: str = self.repo.head.commit.hexsha

        with pytest.raises(GitBaseError, match="was created, but its hook failed"):
            self.repo.commit_and_push_project(
                message="one commit only",
                author_name="Original Author",
                author_email="author@example.org",
                force_empty_commit=True,
            )

        assert self.repo.head.commit.parents[0].hexsha == original_head
        assert self.repo.head.commit.message.strip() == "one commit only"
        sleep.assert_not_called()


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

    def test_description_reads_git_description_without_recursing(self) -> None:
        description = pathlib.Path(self.repo.git_dir) / "description"
        description.write_text("A project description\n")

        assert self.repo.description == "A project description"

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


class GitProcessDeadlineTests(TestCase):
    def test_synchronous_failure_preserves_stdout_and_stderr(self) -> None:
        with pytest.raises(GitCommandError) as error:
            BoundedGit().execute(
                [
                    sys.executable,
                    "-c",
                    "import os, sys; os.write(1, b'output details\\n'); "
                    "os.write(2, b'error details\\n'); sys.exit(3)",
                ]
            )

        assert error.value.status == 3  # noqa: PLR2004
        assert "output details" in error.value.stdout
        assert "error details" in error.value.stderr

    def test_synchronous_output_preserves_bytes_and_exit_status(self) -> None:
        result: tuple[int, bytes, str] = BoundedGit().execute(
            [
                sys.executable,
                "-c",
                "import os, sys; os.write(1, b'\\xff\\n'); "
                "os.write(2, b'warning\\n'); sys.exit(3)",
            ],
            stdout_as_string=False,
            with_extended_output=True,
            with_exceptions=False,
        )

        assert result == (3, b"\xff", "warning")

    def test_output_stream_preserves_trailing_newlines(self) -> None:
        output = BytesIO()

        BoundedGit().execute(
            [sys.executable, "-c", "import os; os.write(1, b'archive bytes\\n\\n')"],
            output_stream=output,
        )

        assert output.getvalue() == b"archive bytes\n\n"

    @override_settings(DJANGO_GIT_COMMAND_TIMEOUT_SECONDS=0.1)
    def test_clone_timeout_terminates_streamed_subprocess(self) -> None:
        """clone_from uses as_process=True, where GitPython ignores its timeout."""
        processes: list[subprocess.Popen[bytes]] = []

        def start_stalled_clone(
            command: list[str], **kwargs: Any
        ) -> subprocess.Popen[bytes]:
            process: subprocess.Popen[bytes] = subprocess.Popen(
                [sys.executable, "-c", "import signal; signal.pause()"],
                **kwargs,
            )
            processes.append(process)
            return process

        with (
            tempfile.TemporaryDirectory() as directory,
            override_settings(DJANGO_GIT_RETRY_ATTEMPTS=1),
            patch("git.cmd.safer_popen", side_effect=start_stalled_clone),
            pytest.raises(GitBaseError, match="deadline"),
        ):
            GitRepo.clone_from(REMOTE_URL, pathlib.Path(directory) / "clone")

        assert len(processes) == 1
        assert processes[0].poll() is not None

    def test_wait_timeout_kills_streamed_process(self) -> None:
        process = BoundedGit().execute(
            [sys.executable, "-c", "import signal; signal.pause()"],
            as_process=True,
            kill_after_timeout=0.1,
        )
        child: subprocess.Popen[bytes] = process.proc

        with pytest.raises(GitCommandError, match="deadline"):
            process.wait()

        assert child.poll() is not None

    def test_timeout_kills_helpers_holding_pipes_after_parent_exits(self) -> None:
        command: str = (
            "import subprocess, sys; "
            "subprocess.Popen([sys.executable, '-c', "
            "'import signal; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            "signal.pause()'])"
        )
        with patch(
            "speleodb.git_engine.operations.os.killpg", wraps=os.killpg
        ) as kill_group:
            process = BoundedGit().execute(
                [sys.executable, "-c", command],
                as_process=True,
                kill_after_timeout=0.5,
            )
            child_pid: int = process.proc.pid

            with pytest.raises(GitCommandError, match="deadline"):
                process.communicate()

        kill_group.assert_any_call(child_pid, signal.SIGKILL)

    def test_successful_parent_still_cleans_up_detached_helper_output(self) -> None:
        command: str = (
            "import subprocess, sys; "
            "subprocess.Popen([sys.executable, '-c', "
            "'import signal; signal.pause()'], "
            "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)"
        )
        with patch(
            "speleodb.git_engine.operations.os.killpg", wraps=os.killpg
        ) as kill_group:
            process = BoundedGit().execute(
                [sys.executable, "-c", command],
                as_process=True,
                kill_after_timeout=5,
            )
            leader: subprocess.Popen[bytes] = process.proc
            process.communicate()
            assert leader.returncode == 0

            assert process.wait() == 0

        kill_group.assert_any_call(leader.pid, signal.SIGKILL)

    @override_settings(DJANGO_GIT_COMMAND_TIMEOUT_SECONDS=0.1)
    def test_synchronous_git_commands_use_configured_deadline(self) -> None:
        with pytest.raises(GitCommandError, match="deadline"):
            BoundedGit().execute(
                [sys.executable, "-c", "import signal; signal.pause()"]
            )

    @override_settings(DJANGO_GIT_COMMAND_TIMEOUT_SECONDS=0.1)
    def test_direct_streamed_commands_cannot_omit_deadline(self) -> None:
        process = BoundedGit().execute(
            [sys.executable, "-c", "import signal; signal.pause()"],
            as_process=True,
        )

        with pytest.raises(GitCommandError, match="deadline"):
            process.communicate()

    def test_only_cat_file_batch_readers_skip_process_deadline(self) -> None:
        for method, options, bounded in (
            ("cat_file", {"batch": True}, False),
            ("cat_file", {"batch_check": True}, False),
            ("cat_file", {"p": True}, True),
            ("log", {}, True),
        ):
            with (
                self.subTest(method=method, options=options),
                patch.object(git.Git, "execute") as execute,
                patch("speleodb.git_engine.operations.DeadlineGitProcess") as deadline,
            ):
                getattr(BoundedGit(), method)(as_process=True, **options)

            assert ("kill_after_timeout" in execute.call_args.kwargs) is bounded
            assert deadline.called is bounded

    @override_settings(DJANGO_GIT_COMMAND_TIMEOUT_SECONDS=7)
    def test_remote_commands_cannot_disable_configured_deadline(self) -> None:
        with patch.object(git.Git, "_call_process", return_value="") as call:
            BoundedGit().clone("remote", "clone", kill_after_timeout=None)

        assert call.call_args.kwargs["kill_after_timeout"] == 7  # noqa: PLR2004
