# -*- coding: utf-8 -*-

from __future__ import annotations

import pathlib
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from io import BytesIO
from unittest import TestCase

import git
import pytest
from django.test import override_settings
from git.exc import GitCommandError

from speleodb.git_engine.core import GIT_COMMITTER
from speleodb.git_engine.core import GitCommit
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.exceptions import GitBaseError
from speleodb.git_engine.operations import BoundedGit
from speleodb.git_engine.operations import DeadlineGitProcess
from speleodb.utils.user_identity import DEFAULT_USER_NAME

ENCODED_CREDENTIAL: str = "test%40credential"
DECODED_CREDENTIAL: str = "test@credential"
RETRY_ATTEMPTS: int = 5


def assert_credentials_redacted(diagnostic_text: str) -> None:
    assert ENCODED_CREDENTIAL not in diagnostic_text
    assert DECODED_CREDENTIAL not in diagnostic_text
    assert "oauth2:" not in diagnostic_text
    assert "127.0.0.1" in diagnostic_text
    assert any(f"exit code({code})" in diagnostic_text for code in (1, 128))


def assert_process_stopped(pid: int) -> None:
    """A killed orphan can briefly remain as a zombie until its parent reaps it."""
    executable: str | None = shutil.which("ps")
    assert executable is not None
    deadline: float = time.monotonic() + 3
    while True:
        result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
            [executable, "-o", "stat=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        if result.returncode != 0 or result.stdout.strip().startswith("Z"):
            return
        assert time.monotonic() < deadline, f"Git helper {pid} is still running"
        time.sleep(0.01)


class LocalGitTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.root: pathlib.Path = pathlib.Path(
            self.enterContext(tempfile.TemporaryDirectory())
        )
        self.enterContext(
            override_settings(
                DJANGO_GIT_RETRY_ATTEMPTS=RETRY_ATTEMPTS,
                DJANGO_GIT_RETRY_BASE_DELAY_SECONDS=0.05,
                DJANGO_GIT_RETRY_MAX_DELAY_SECONDS=0.1,
            )
        )
        self.remote: git.Repo = git.Repo.init(self.root / "remote.git", bare=True)
        self.addCleanup(self.remote.close)
        self.repo: GitRepo = GitRepo.init(self.root / "working")
        self.addCleanup(self.repo.close)
        (self.repo.path / "README.txt").write_text("initial", encoding="utf-8")
        self.repo.index.add(["README.txt"])
        self.repo.index.commit("initial commit", author=GIT_COMMITTER)
        self.repo.create_remote("origin", url=str(self.remote.git_dir))
        self.repo.git.push("--set-upstream", "origin", self.repo.active_branch.name)
        self.unavailable: socket.socket = self.enterContext(socket.socket())
        self.unavailable.bind(("127.0.0.1", 0))
        self.remote_url: str = (
            f"http://oauth2:{ENCODED_CREDENTIAL}@127.0.0.1:"
            f"{self.unavailable.getsockname()[1]}/project.git"
        )

    def _hook(self, repository: git.Repo, name: str, failures: int) -> pathlib.Path:
        """Use a real Git hook to reject a fixed number of attempts."""
        count: pathlib.Path = self.root / f"{name}-attempts"
        script: str = (
            f"#!{sys.executable}\n"
            "from pathlib import Path\n"
            "import sys\n"
            f"counter = Path({str(count)!r})\n"
            "attempt = int(counter.read_text()) + 1 if counter.exists() else 1\n"
            "counter.write_text(str(attempt))\n"
            f"if attempt <= {failures}:\n"
            "    print('test hook rejected operation', file=sys.stderr)\n"
            "    sys.exit(1)\n"
        )
        hook: pathlib.Path = pathlib.Path(repository.git_dir) / "hooks" / name
        hook.write_text(script, encoding="utf-8")
        hook.chmod(0o755)
        return count

    def _commit_and_push(self) -> str | None:
        return self.repo.commit_and_push_project(
            message="test revision", author_name="Test", author_email="test@test.local"
        )

    def _release_after_first_retry(
        self, source: pathlib.Path, target: pathlib.Path | None = None
    ) -> threading.Thread:
        # Git's first failed operation is captured in Trace2 before the resource
        # is restored. A real filesystem lock/remote disappearance causes failure.
        trace: pathlib.Path = self.root / "git-trace.json"
        self.repo.git.update_environment(GIT_TRACE2_EVENT=str(trace))

        def restore() -> None:
            deadline: float = time.monotonic() + 5
            while time.monotonic() < deadline:
                if trace.exists() and '"event":"error"' in trace.read_text():
                    if target is None:
                        source.unlink()
                    else:
                        source.rename(target)
                    return
                time.sleep(0.005)

        thread: threading.Thread = threading.Thread(target=restore, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 6)
        return thread


class CommitAndPushRetryTests(LocalGitTests):
    """Retry genuine Git lock/hook failures, then inspect the remote commits."""

    def test_index_add_retries_after_real_lock_is_released(self) -> None:
        (self.repo.path / "newfile.txt").write_text("content", encoding="utf-8")
        lock: pathlib.Path = pathlib.Path(self.repo.git_dir) / "index.lock"
        lock.touch()
        released: threading.Thread = self._release_after_first_retry(lock)
        with self.assertLogs("speleodb.utils.helpers", level="DEBUG") as logs:
            result: str | None = self._commit_and_push()
        released.join(timeout=6)
        assert not released.is_alive()
        assert result == self.remote.commit(self.repo.active_branch.name).hexsha
        assert "index.lock" in "\n".join(logs.output)

    def test_commit_retries_after_pre_commit_hook_rejection(self) -> None:
        (self.repo.path / "newfile.txt").write_text("content", encoding="utf-8")
        attempts: pathlib.Path = self._hook(self.repo, "pre-commit", failures=1)
        result: str | None = self._commit_and_push()
        assert attempts.read_text() == "2"
        assert result == self.remote.commit(self.repo.active_branch.name).hexsha

    def test_push_retries_after_pre_receive_hook_rejection(self) -> None:
        (self.repo.path / "newfile.txt").write_text("content", encoding="utf-8")
        attempts: pathlib.Path = self._hook(self.remote, "pre-receive", failures=1)
        original: str = self.repo.head.commit.hexsha
        result: str | None = self._commit_and_push()
        assert attempts.read_text() == "2"
        assert result == self.remote.commit(self.repo.active_branch.name).hexsha
        assert self.repo.head.commit.parents[0].hexsha == original

    def test_index_add_raises_after_persistent_lock(self) -> None:
        original: str = self.repo.head.commit.hexsha
        (self.repo.path / "newfile.txt").write_text("content", encoding="utf-8")
        lock: pathlib.Path = pathlib.Path(self.repo.git_dir) / "index.lock"
        lock.touch()
        with (
            self.assertLogs("speleodb.utils.helpers", level="DEBUG") as logs,
            pytest.raises(GitCommandError, match=r"index\.lock"),
        ):
            self._commit_and_push()
        assert len(logs.records) == RETRY_ATTEMPTS - 1
        assert lock.exists()
        assert self.repo.head.commit.hexsha == original
        assert self.remote.commit(self.repo.active_branch.name).hexsha == original

    def test_commit_raises_after_persistent_pre_commit_rejection(self) -> None:
        original: str = self.repo.head.commit.hexsha
        (self.repo.path / "newfile.txt").write_text("content", encoding="utf-8")
        attempts: pathlib.Path = self._hook(self.repo, "pre-commit", RETRY_ATTEMPTS)
        with pytest.raises(GitCommandError, match="test hook rejected operation"):
            self._commit_and_push()
        assert int(attempts.read_text()) == RETRY_ATTEMPTS
        assert self.repo.head.commit.hexsha == original
        assert self.remote.commit(self.repo.active_branch.name).hexsha == original

    def test_push_raises_redacted_error_after_exhausted_retries(self) -> None:
        (self.repo.path / "newfile.txt").write_text("content", encoding="utf-8")
        original: str = self.repo.head.commit.hexsha
        self.repo.remotes.origin.set_url(self.remote_url)
        with (
            self.assertLogs("speleodb.utils.helpers", level="DEBUG") as logs,
            pytest.raises(GitBaseError, match="Impossible to push") as raised,
        ):
            self._commit_and_push()
        assert len(logs.records) == RETRY_ATTEMPTS - 1
        assert_credentials_redacted(
            "\n".join([*traceback.format_exception(raised.value), *logs.output])
        )
        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None
        assert self.repo.head.commit.parents[0].hexsha == original
        assert self.remote.commit(self.repo.active_branch.name).hexsha == original

    def test_staging_includes_upload_artifacts_ignored_by_repository_rules(
        self,
    ) -> None:
        ignored_file: pathlib.Path = self.repo.path / "survey.dat"
        (self.repo.path / ".gitignore").write_text("*.dat\n", encoding="utf-8")
        ignored_file.write_text("uploaded survey", encoding="utf-8")
        assert self.repo.git.check_ignore(str(ignored_file))

        result: str | None = self._commit_and_push()

        assert result is not None
        committed: git.Commit = self.remote.commit(self.repo.active_branch.name)
        assert committed.hexsha == result
        assert (committed.tree / "survey.dat").data_stream.read() == b"uploaded survey"

    def test_supervised_commit_preserves_author_and_committer(self) -> None:
        commit: GitCommit = self.repo._commit_project(  # noqa: SLF001
            "authored commit", author=git.Actor("Original Author", "author@example.org")
        )
        assert commit.message == "authored commit"
        assert commit.author.name == "Original Author"
        assert commit.author.email == "author@example.org"
        assert commit.committer == GIT_COMMITTER

    def test_commit_and_push_uses_fallback_for_unusable_author_names(self) -> None:
        names: tuple[str, ...] = (
            "",
            " \t\r\n ",
            "\u00a0\u2003",
            "<>",
            ".",
            "...",
            ".,:;<>\"\\'",
            "\x00\x01\x1f",
        )
        attempts: pathlib.Path = self._hook(self.repo, "pre-commit", failures=0)
        for index, author_name in enumerate(names, start=1):
            with self.subTest(author_name=author_name):
                original: str = self.repo.head.commit.hexsha
                message: str = f"Fallback author {index}"
                result: str | None = self.repo.commit_and_push_project(
                    message=message,
                    author_name=author_name,
                    author_email="original-author@example.org",
                    force_empty_commit=True,
                )
                committed: git.Commit = self.remote.commit(self.repo.active_branch.name)
                assert result == committed.hexsha
                assert committed.message == message
                assert committed.author.name == DEFAULT_USER_NAME
                assert committed.author.email == "original-author@example.org"
                assert committed.committer == GIT_COMMITTER
                assert [parent.hexsha for parent in committed.parents] == [original]
                assert attempts.read_text() == str(index)

    def test_supervised_commit_uses_fallback_for_missing_actor_name(self) -> None:
        commit: GitCommit = self.repo._commit_project(  # noqa: SLF001
            "missing actor name", author=git.Actor(None, "author@example.org")
        )
        assert commit.author.name == DEFAULT_USER_NAME
        assert commit.author.email == "author@example.org"
        assert commit.committer == GIT_COMMITTER

    def test_commit_and_push_preserves_usable_author_names(self) -> None:
        names: tuple[tuple[str, str], ...] = (
            ("Ada Lovelace", "Ada Lovelace"),
            ("Élodie 李", "Élodie 李"),
            ("O'Connor", "O'Connor"),
            ("Dr. Alice", "Dr. Alice"),
            ("  Alice  ", "Alice"),
            ("<Alice>", "Alice"),
        )
        for author_name, expected_name in names:
            with self.subTest(author_name=author_name):
                result: str | None = self.repo.commit_and_push_project(
                    message="preserve usable author",
                    author_name=author_name,
                    author_email="author@example.org",
                    force_empty_commit=True,
                )
                committed: git.Commit = self.remote.commit(self.repo.active_branch.name)
                assert result == committed.hexsha
                assert committed.author.name == expected_name
                assert committed.author.email == "author@example.org"
                assert committed.committer == GIT_COMMITTER

    @override_settings(DJANGO_GIT_COMMAND_TIMEOUT_SECONDS=0.5)
    def test_post_commit_timeout_does_not_retry_completed_commit(self) -> None:
        hook: pathlib.Path = pathlib.Path(self.repo.git_dir) / "hooks" / "post-commit"
        hook.write_text(
            f"#!/bin/sh\nexec {shlex.quote(sys.executable)} -c "
            "'import signal; signal.pause()'\n"
        )
        hook.chmod(0o755)
        original: str = self.repo.head.commit.hexsha
        with pytest.raises(GitBaseError, match="was created, but its hook failed"):
            self.repo.commit_and_push_project(
                "one commit only",
                "Original Author",
                "author@example.org",
                force_empty_commit=True,
            )
        assert self.repo.head.commit.parents[0].hexsha == original
        assert self.repo.head.commit.message.strip() == "one commit only"
        assert self.remote.commit(self.repo.active_branch.name).hexsha == original


class PullAndFetchRetryTests(LocalGitTests):
    def test_description_reads_git_description_without_recursing(self) -> None:
        description: pathlib.Path = pathlib.Path(self.repo.git_dir) / "description"
        description.write_text("A project description\n")
        assert self.repo.description == "A project description"

    def test_pull_and_fetch_retry_when_real_remote_returns(self) -> None:
        for operation in ("pull", "fetch"):
            with self.subTest(operation=operation):
                trace: pathlib.Path = self.root / "git-trace.json"
                trace.unlink(missing_ok=True)
                remote_path: pathlib.Path = pathlib.Path(self.remote.git_dir)
                unavailable: pathlib.Path = self.root / "unavailable.git"
                remote_path.rename(unavailable)
                restored: threading.Thread = self._release_after_first_retry(
                    unavailable, remote_path
                )
                with self.assertLogs("speleodb.utils.helpers", level="DEBUG") as logs:
                    getattr(self.repo, operation)()
                restored.join(timeout=6)
                assert not restored.is_alive()
                assert "does not appear to be a git repository" in "\n".join(
                    logs.output
                )
                assert (
                    self.repo.head.commit.hexsha
                    == self.remote.commit(self.repo.active_branch.name).hexsha
                )

    def test_pull_and_fetch_raise_redacted_errors_after_exhaustion(self) -> None:
        self.repo.remotes.origin.set_url(self.remote_url)
        for operation in ("pull", "fetch"):
            with (
                self.subTest(operation=operation),
                self.assertLogs("speleodb.utils.helpers", level="DEBUG") as logs,
                pytest.raises(
                    GitBaseError, match=f"Impossible to {operation}"
                ) as raised,
            ):
                getattr(self.repo, operation)()
            assert len(logs.records) == RETRY_ATTEMPTS - 1
            assert_credentials_redacted(
                "\n".join([*traceback.format_exception(raised.value), *logs.output])
            )
            assert raised.value.__cause__ is None
            assert raised.value.__context__ is None

    def test_set_origin_url_raises_redacted_error_after_config_lock(self) -> None:
        lock: pathlib.Path = pathlib.Path(self.repo.git_dir) / "config.lock"
        lock.touch()
        with (
            self.assertLogs("speleodb.utils.helpers", level="DEBUG") as logs,
            pytest.raises(
                GitBaseError, match="Impossible to configure origin"
            ) as raised,
        ):
            self.repo.set_origin_url(self.remote_url)
        assert len(logs.records) == RETRY_ATTEMPTS - 1
        assert_credentials_redacted(
            "\n".join([*traceback.format_exception(raised.value), *logs.output])
        )
        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None
        assert self.repo.remotes.origin.url == str(self.remote.git_dir)


class CloneRetryTests(LocalGitTests):
    def test_clone_retries_when_real_remote_returns(self) -> None:
        remote_path: pathlib.Path = pathlib.Path(self.remote.git_dir)
        unavailable: pathlib.Path = self.root / "unavailable.git"
        remote_path.rename(unavailable)
        # Clone accepts Git's environment directly; the watcher observes the
        # actual failed subprocess before restoring the unavailable directory.
        restored: threading.Thread = self._release_after_first_retry(
            unavailable, remote_path
        )
        with self.assertLogs("speleodb.utils.helpers", level="DEBUG") as logs:
            cloned: GitRepo = GitRepo.clone_from(
                str(remote_path),
                self.root / "clone",
                env={"GIT_TRACE2_EVENT": str(self.root / "git-trace.json")},
            )
        self.addCleanup(cloned.close)
        restored.join(timeout=6)
        assert not restored.is_alive()
        assert cloned.head.commit.hexsha == self.repo.head.commit.hexsha
        assert "does not exist" in "\n".join(logs.output)

    def test_clone_raises_redacted_error_after_retries(self) -> None:
        for keyword_url in (False, True):
            arguments: tuple[str, pathlib.Path] | tuple[()] = (
                () if keyword_url else (self.remote_url, self.root / "clone")
            )
            options: dict[str, str | pathlib.Path] = (
                {"url": self.remote_url, "to_path": self.root / "clone"}
                if keyword_url
                else {}
            )
            with (
                self.subTest(keyword_url=keyword_url),
                self.assertLogs("speleodb.utils.helpers", level="DEBUG") as logs,
                pytest.raises(GitBaseError, match="Impossible to clone") as raised,
            ):
                GitRepo.clone_from(*arguments, **options)
            assert len(logs.records) == RETRY_ATTEMPTS - 1
            assert_credentials_redacted(
                "\n".join([*traceback.format_exception(raised.value), *logs.output])
            )
            assert raised.value.__cause__ is None
            assert raised.value.__context__ is None
            assert not (self.root / "clone").exists()


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
        output: BytesIO = BytesIO()
        BoundedGit().execute(
            [sys.executable, "-c", "import os; os.write(1, b'archive bytes\\n\\n')"],
            output_stream=output,
        )
        assert output.getvalue() == b"archive bytes\n\n"

    def _stalled_pack_hook(
        self, root: pathlib.Path
    ) -> tuple[git.Repo, pathlib.Path, str]:
        remote: git.Repo = git.Repo.init(root / "remote")
        self.addCleanup(remote.close)
        remote.index.commit("initial", author=GIT_COMMITTER)
        pid_file: pathlib.Path = root / "pack-objects.pid"
        hook: pathlib.Path = root / "pack-objects-hook"
        hook.write_text(
            f"#!{sys.executable}\nimport os, signal\nfrom pathlib import Path\n"
            f"Path({str(pid_file)!r}).write_text(str(os.getpid()))\nsignal.pause()\n"
        )
        hook.chmod(0o755)
        # Git's actual upload-pack runs its native packObjectsHook. The hook
        # blocks object generation after the real clone protocol negotiation.
        upload_pack: str = (
            f"git -c uploadpack.packObjectsHook={shlex.quote(str(hook))} upload-pack"
        )
        return remote, pid_file, upload_pack

    @override_settings(
        DJANGO_GIT_COMMAND_TIMEOUT_SECONDS=0.5, DJANGO_GIT_RETRY_ATTEMPTS=1
    )
    def test_clone_timeout_terminates_actual_upload_pack_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root: pathlib.Path = pathlib.Path(directory)
            remote: git.Repo
            pid_file: pathlib.Path
            upload_pack: str
            remote, pid_file, upload_pack = self._stalled_pack_hook(root)
            with pytest.raises(GitBaseError, match="deadline"):
                GitRepo.clone_from(
                    f"file://{remote.working_dir}",
                    root / "clone",
                    upload_pack=upload_pack,
                    allow_unsafe_options=True,
                )
            assert_process_stopped(int(pid_file.read_text()))

    def test_wait_timeout_kills_streamed_process(self) -> None:
        process: DeadlineGitProcess = BoundedGit().execute(
            [sys.executable, "-c", "import signal; signal.pause()"],
            as_process=True,
            kill_after_timeout=0.1,
        )
        child: subprocess.Popen[bytes] | None = process.proc
        assert child is not None
        with pytest.raises(GitCommandError, match="deadline"):
            process.wait()
        assert child.poll() is not None

    def _helper_process(self, *, detached: bool) -> tuple[DeadlineGitProcess, int]:
        root: pathlib.Path = pathlib.Path(
            self.enterContext(tempfile.TemporaryDirectory())
        )
        pid_file: pathlib.Path = root / "helper.pid"
        helper: str = (
            "import os, signal; from pathlib import Path; "
            f"Path({str(pid_file)!r}).write_text(str(os.getpid())); "
            "signal.signal(signal.SIGTERM, signal.SIG_IGN); signal.pause()"
        )
        command: str = (
            "import subprocess, sys, time; from pathlib import Path; "
            f"subprocess.Popen([sys.executable, '-c', {helper!r}]"
            + (
                ", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL"
                if detached
                else ""
            )
            + f"); marker=Path({str(pid_file)!r}); "
            "\nwhile not marker.exists(): time.sleep(0.001)"
        )
        process: DeadlineGitProcess = BoundedGit().execute(
            [sys.executable, "-c", command],
            as_process=True,
            kill_after_timeout=0.5,
        )
        deadline: float = time.monotonic() + 2
        while not pid_file.exists():
            assert time.monotonic() < deadline
            time.sleep(0.005)
        pid: int = int(pid_file.read_text())
        return process, pid

    def test_timeout_kills_helpers_holding_pipes_after_parent_exits(self) -> None:
        process: DeadlineGitProcess
        pid: int
        process, pid = self._helper_process(detached=False)
        with pytest.raises(GitCommandError, match="deadline"):
            process.communicate()
        assert_process_stopped(pid)

    def test_successful_parent_cleans_up_detached_helper(self) -> None:
        process: DeadlineGitProcess
        pid: int
        process, pid = self._helper_process(detached=True)
        process.communicate()
        assert process.wait() == 0
        assert_process_stopped(pid)

    @override_settings(DJANGO_GIT_COMMAND_TIMEOUT_SECONDS=0.1)
    def test_synchronous_git_commands_use_configured_deadline(self) -> None:
        with pytest.raises(GitCommandError, match="deadline"):
            BoundedGit().execute(
                [sys.executable, "-c", "import signal; signal.pause()"]
            )

    @override_settings(DJANGO_GIT_COMMAND_TIMEOUT_SECONDS=0.1)
    def test_direct_streamed_commands_cannot_omit_deadline(self) -> None:
        process: DeadlineGitProcess = BoundedGit().execute(
            [sys.executable, "-c", "import signal; signal.pause()"],
            as_process=True,
        )
        with pytest.raises(GitCommandError, match="deadline"):
            process.communicate()

    @override_settings(DJANGO_GIT_COMMAND_TIMEOUT_SECONDS=0.1)
    def test_only_cat_file_batch_readers_skip_process_deadline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo: git.Repo = git.Repo.init(directory)
            self.addCleanup(repo.close)
            repo.index.commit("initial", author=GIT_COMMITTER)
            command: BoundedGit = BoundedGit(directory)
            for option in ("batch", "batch_check"):
                process: git.Git.AutoInterrupt = command.cat_file(
                    as_process=True, istream=subprocess.PIPE, **{option: True}
                )
                try:
                    assert not isinstance(process, DeadlineGitProcess)
                    time.sleep(0.15)
                    assert process.proc is not None
                    assert process.proc.poll() is None
                    process.stdin.write(b"HEAD\n")
                    process.stdin.flush()
                    assert repo.head.commit.hexsha.encode() in process.stdout.readline()
                finally:
                    process._terminate()  # noqa: SLF001
            for operation, arguments in (
                ("cat_file", ("-p", "HEAD")),
                ("log", ("-1",)),
            ):
                bounded: DeadlineGitProcess = getattr(command, operation)(
                    *arguments, as_process=True
                )
                assert isinstance(bounded, DeadlineGitProcess)
                bounded.communicate()
                assert bounded.wait() == 0

    @override_settings(DJANGO_GIT_COMMAND_TIMEOUT_SECONDS=0.5)
    def test_remote_commands_cannot_disable_configured_deadline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root: pathlib.Path = pathlib.Path(directory)
            remote: git.Repo
            pid_file: pathlib.Path
            upload_pack: str
            remote, pid_file, upload_pack = self._stalled_pack_hook(root)
            with pytest.raises(GitCommandError, match="deadline"):
                BoundedGit().clone(
                    f"file://{remote.working_dir}",
                    str(root / "clone"),
                    upload_pack=upload_pack,
                    kill_after_timeout=None,
                )
            assert_process_stopped(int(pid_file.read_text()))
