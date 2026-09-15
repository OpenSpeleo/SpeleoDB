from __future__ import annotations

import contextlib
import math
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from typing import TYPE_CHECKING
from typing import Any
from typing import override
from urllib.parse import unquote
from urllib.parse import urlsplit

from django.conf import settings
from git import Git
from git.compat import safe_decode
from git.exc import GitCommandError

from speleodb.git_engine.exceptions import GitBaseError
from speleodb.utils.helpers import retry_with_backoff

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence

_PERSISTENT_CAT_FILE_TIMEOUT: object = object()


def _kill_git_process_group(pid: int, expired: threading.Event) -> None:
    """Do not close pipes here: reader threads may hold their Python locks."""
    expired.set()
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pid, signal.SIGKILL)


class DeadlineGitProcess(Git.AutoInterrupt):
    """Bound streamed Git commands, which GitPython's execute timeout ignores."""

    def __init__(
        self,
        process: subprocess.Popen[Any],
        args: Any,
        timeout: float,
    ) -> None:
        super().__init__(process, args)
        self._deadline: float = time.monotonic() + timeout
        self._timeout: float = timeout
        self._expired: threading.Event = threading.Event()
        self._watchdog: threading.Timer = threading.Timer(
            timeout, _kill_git_process_group, (process.pid, self._expired)
        )
        self._watchdog.daemon = True
        self._watchdog.start()

    def _timeout_error(self) -> GitCommandError:
        return GitCommandError(
            self.args,
            "timeout",
            stderr=f"Git command exceeded its {self._timeout:g}s deadline",
        )

    @override
    def _terminate(self) -> None:
        # GitPython closes pipes before TERM and then calls an unbounded wait().
        # Kill the isolated process group first, including helpers/hooks, and
        # bound cleanup even if a process cannot immediately be reaped.
        process: subprocess.Popen[Any] | None = self.proc
        if process is None:
            self._watchdog.cancel()
            return
        # The leader may have exited while a helper still owns the group.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        try:
            self.status = process.wait(
                timeout=settings.DJANGO_GIT_PROCESS_CLEANUP_TIMEOUT_SECONDS
            )
        except subprocess.TimeoutExpired:
            self.status = -signal.SIGKILL
        finally:
            self._watchdog.cancel()
            self.proc = None

    def communicate(
        self,
        input: str | bytes | None = None,  # noqa: A002
        timeout: float | None = None,
    ) -> tuple[Any, Any]:
        process: subprocess.Popen[Any] | None = self.proc
        if process is None:
            raise RuntimeError("Git process has already been released")
        remaining: float = max(0.0, self._deadline - time.monotonic())
        if timeout is not None:
            remaining = min(remaining, timeout)
        try:
            result: tuple[Any, Any] = process.communicate(input, timeout=remaining)
        except subprocess.TimeoutExpired:
            self._expired.set()
            self._terminate()
            raise self._timeout_error() from None
        if self._expired.is_set():
            raise self._timeout_error()
        return result

    @override
    def wait(
        self,
        stderr: str | bytes | None = b"",
        *,
        with_exceptions: bool = True,
    ) -> int:
        try:
            status: int | None = self.status
            if self.proc is not None:
                status = self.proc.wait(
                    timeout=max(0.0, self._deadline - time.monotonic())
                )
            if self._expired.is_set():
                raise self._timeout_error()
            # Callers have already consumed the process streams. Preserve the
            # GitPython return-code check and original stderr diagnostics.
            if with_exceptions:
                return super().wait(stderr=stderr)
            assert status is not None
            return status
        except subprocess.TimeoutExpired:
            self._expired.set()
            self._terminate()
            raise self._timeout_error() from None
        finally:
            self._terminate()


class BoundedGit(Git):
    """Apply process deadlines without replacing GitPython's clone validation."""

    @override
    def _call_process(self, method: str, *args: Any, **kwargs: Any) -> Any:
        if (
            method == "cat_file"
            and kwargs.get("as_process", False)
            and (kwargs.get("batch", False) or kwargs.get("batch_check", False))
            and kwargs.get("kill_after_timeout") is None
        ):
            # GitPython only forwards its known execute kwargs. A private
            # sentinel marks these intentionally reusable object readers.
            kwargs["kill_after_timeout"] = _PERSISTENT_CAT_FILE_TIMEOUT
        elif kwargs.get("kill_after_timeout") is None:
            kwargs["kill_after_timeout"] = settings.DJANGO_GIT_COMMAND_TIMEOUT_SECONDS
        return super()._call_process(method, *args, **kwargs)

    def _command_output(self, command: str | Sequence[Any], **kwargs: Any) -> Any:
        kwargs["as_process"] = True
        process: DeadlineGitProcess = self.execute(command, **kwargs)
        output_stream: Any = kwargs.get("output_stream")
        stdout: str | bytes | None
        stderr: str | bytes | None
        if output_stream is None:
            stdout, stderr = process.communicate()
        else:
            # Preserve GitPython's streaming contract for archive/file output.
            # The group deadline also terminates helpers retaining these pipes.
            if process.stdout is not None:
                shutil.copyfileobj(process.stdout, output_stream)
            stderr = process.stderr.read() if process.stderr is not None else None
            stdout = None
        status: int = process.wait(stderr=stderr, with_exceptions=False)
        if stdout is not None and kwargs.get("strip_newline_in_stdout", True):
            stdout = (
                stdout.removesuffix("\n")
                if isinstance(stdout, str)
                else stdout.removesuffix(b"\n")
            )
        if stderr is not None:
            stderr = (
                stderr.removesuffix("\n")
                if isinstance(stderr, str)
                else stderr.removesuffix(b"\n")
            )
        if status and kwargs.get("with_exceptions", True):
            error_command: str | list[str] = (
                command if isinstance(command, str) else [str(part) for part in command]
            )
            raise GitCommandError(error_command, status, stderr, stdout)
        if output_stream is not None:
            stdout = output_stream
        elif stdout is not None and kwargs.get("stdout_as_string", True):
            stdout = safe_decode(stdout)
        if kwargs.get("with_extended_output", False):
            return status, stdout, safe_decode(stderr) if stderr is not None else ""
        return stdout

    @override
    def execute(self, command: str | Sequence[Any], **kwargs: Any) -> Any:
        if kwargs.get("kill_after_timeout") is _PERSISTENT_CAT_FILE_TIMEOUT:
            kwargs.pop("kill_after_timeout")
            return super().execute(command, **kwargs)
        timeout: float | None = kwargs.get("kill_after_timeout")
        if not kwargs.get("as_process", False):
            timeout = (
                settings.DJANGO_GIT_COMMAND_TIMEOUT_SECONDS
                if timeout is None
                else timeout
            )
            if not math.isfinite(timeout) or timeout <= 0:
                raise ValueError("Git command timeout must be finite and positive")
            kwargs["kill_after_timeout"] = timeout
            return self._command_output(command, **kwargs)
        if timeout is None:
            timeout = settings.DJANGO_GIT_COMMAND_TIMEOUT_SECONDS
            kwargs["kill_after_timeout"] = timeout
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Git command timeout must be finite and positive")
        kwargs["start_new_session"] = True
        process: Git.AutoInterrupt = super().execute(command, **kwargs)
        child: subprocess.Popen[Any] | None = process.proc
        if child is None:
            raise RuntimeError("Git command did not start a process")
        timed_process: DeadlineGitProcess = DeadlineGitProcess(
            child, process.args, timeout
        )
        # Transfer ownership so the temporary wrapper cannot kill the command.
        process.proc = None
        return timed_process


def retry_git_operation[RT](
    operation: Callable[..., RT],
    *args: Any,
    remote_url: str,
    action: str,
    **kwargs: Any,
) -> RT:
    """Retry remote Git commands without exposing credentials to retry logs."""
    parsed_url = urlsplit(remote_url)
    raw_userinfo = (
        parsed_url.netloc.rpartition("@")[0] if "@" in parsed_url.netloc else ""
    )
    raw_credential = (
        raw_userinfo.partition(":")[2] if ":" in raw_userinfo else raw_userinfo
    )
    credential_variants = {
        credential
        for credential in (raw_credential, unquote(raw_credential))
        if credential
    }
    credential_url_pattern = re.compile(
        r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^/@\s'\"<>]+@",
        flags=re.IGNORECASE,
    )

    def redact_credentials(value: object) -> str:
        redacted = str(value)
        for credential in sorted(credential_variants, key=len, reverse=True):
            redacted = redacted.replace(credential, "[REDACTED]")
        return credential_url_pattern.sub(r"\g<scheme>", redacted)

    def run_with_sanitized_errors() -> RT:
        sanitized_error: GitBaseError
        try:
            return operation(*args, **kwargs)
        except GitCommandError as error:
            sanitized_error = GitBaseError(
                f"Impossible to {action} repository: "
                f"url={redact_credentials(remote_url)!r}. {redact_credentials(error)}"
            )
        # Outside the handler: no credential-bearing context survives either.
        raise sanitized_error from None

    return retry_with_backoff(
        run_with_sanitized_errors,
        retries=settings.DJANGO_GIT_RETRY_ATTEMPTS,
        exc_types=(GitBaseError,),
        base_delay=settings.DJANGO_GIT_RETRY_BASE_DELAY_SECONDS,
        max_delay=settings.DJANGO_GIT_RETRY_MAX_DELAY_SECONDS,
    )
