"""Real process containment against a TCP endpoint that accepts but stalls."""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

import pytest

from speleodb.background_jobs import archive_sources
from speleodb.background_jobs import git_supervisor
from speleodb.background_jobs.archive_sources import ArchiveBuildError
from speleodb.background_jobs.git_supervisor import TIMEOUT_EXIT_CODE

if TYPE_CHECKING:
    from collections.abc import Generator


pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="Production process containment runs in Linux."
)

OWNER_SCRIPT: str = """
import sys
from pathlib import Path
import django
django.setup()
from speleodb.background_jobs.archive_sources import GitSource, mirror_project
mirror_project(GitSource(sys.argv[2], ""), Path(sys.argv[1]), heartbeat=lambda: None)
"""
HELPER_SCRIPT: str = """
import os
import signal
import sys
import time
from pathlib import Path
signal.signal(signal.SIGTERM, signal.SIG_IGN)
Path(sys.argv[1]).write_text(str(os.getpid()))
time.sleep(60)
"""
LEADER_SCRIPT: str = """
import os
import subprocess
import sys
import time
from pathlib import Path
subprocess.Popen([sys.executable, sys.argv[1], sys.argv[2]])
while not Path(sys.argv[3]).exists():
    time.sleep(0.01)
os._exit(0)
"""
SUPERVISOR: Path = Path(__file__).parents[1] / "git_supervisor.py"
WAIT_SECONDS: int = 15
MIN_GIT_PROCESSES: int = 3


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_supervisor_rejects_unbounded_deadline(timeout: float) -> None:
    with (
        patch("speleodb.background_jobs.git_supervisor.subprocess.Popen") as start,
        pytest.raises(ValueError, match="finite and positive"),
    ):
        git_supervisor.supervise(parent_fd=-1, timeout=timeout, command=["git"])
    start.assert_not_called()


def test_group_cleanup_remains_bounded_after_kill() -> None:
    process: MagicMock = MagicMock(pid=12345)
    process.wait.side_effect = subprocess.TimeoutExpired("git", 5)
    with (
        patch("speleodb.background_jobs.git_supervisor.os.killpg") as kill_group,
        pytest.raises(subprocess.TimeoutExpired),
    ):
        git_supervisor._terminate_group(process)  # noqa: SLF001
    assert kill_group.call_args_list == [
        call(process.pid, signal.SIGTERM),
        call(process.pid, signal.SIGKILL),
    ]
    assert process.wait.call_args_list == [
        call(timeout=git_supervisor.TERMINATE_SECONDS),
        call(timeout=git_supervisor.TERMINATE_SECONDS),
    ]


def test_export_waits_for_full_supervisor_cleanup_then_bounds_reaping() -> None:
    process: MagicMock = MagicMock()
    process.wait.side_effect = subprocess.TimeoutExpired("supervisor", 5)
    with pytest.raises(ArchiveBuildError, match="could not be stopped"):
        archive_sources._stop_supervisor(process)  # noqa: SLF001
    process.kill.assert_called_once_with()
    assert process.wait.call_args_list == [
        call(
            timeout=2 * git_supervisor.TERMINATE_SECONDS
            + 2 * archive_sources.GIT_POLL_SECONDS
        ),
        call(timeout=git_supervisor.TERMINATE_SECONDS),
    ]


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    started: str
    command: str
    state: str


def _identity(pid: int) -> ProcessIdentity | None:
    try:
        stat: str = Path(f"/proc/{pid}/stat").read_text()
    except FileNotFoundError:
        return None
    prefix: str
    suffix: str
    prefix, suffix = stat.rsplit(")", 1)
    fields: list[str] = suffix.split()
    return ProcessIdentity(pid, fields[19], prefix.split("(", 1)[1], fields[0])


def _descendants(parent_pid: int) -> list[ProcessIdentity]:
    descendants: list[ProcessIdentity] = []
    remaining: list[int] = [parent_pid]
    while remaining:
        pid: int = remaining.pop()
        try:
            children: str = Path(f"/proc/{pid}/task/{pid}/children").read_text()
        except FileNotFoundError:
            continue
        for child in children.split():
            identity: ProcessIdentity | None = _identity(int(child))
            if identity is not None:
                descendants.append(identity)
                remaining.append(identity.pid)
    return descendants


def _running(identity: ProcessIdentity) -> bool:
    current: ProcessIdentity | None = _identity(identity.pid)
    # An orphan may await PID 1 reaping, but must no longer execute or own FDs.
    return (
        current is not None
        and current.started == identity.started
        and current.state not in {"Z", "X"}
    )


def _assert_stopped(identities: list[ProcessIdentity]) -> None:
    deadline: float = time.monotonic() + WAIT_SECONDS
    while any(_running(identity) for identity in identities):
        assert time.monotonic() < deadline, "Git or its helpers survived owner death."
        time.sleep(0.05)


def _cleanup(
    process: subprocess.Popen[bytes], identities: list[ProcessIdentity]
) -> None:
    if process.poll() is None:
        process.kill()
        process.wait(timeout=WAIT_SECONDS)
    for identity in identities:
        if _running(identity):
            with contextlib.suppress(ProcessLookupError):
                os.kill(identity.pid, signal.SIGKILL)


@pytest.fixture
def stalled_git_endpoint() -> Generator[tuple[str, threading.Event]]:
    connected = threading.Event()
    finished = threading.Event()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(0.1)

        def accept() -> None:
            while not finished.is_set():
                try:
                    connection, _ = listener.accept()
                except TimeoutError:
                    continue
                with connection:
                    connection.settimeout(WAIT_SECONDS)
                    connection.recv(8192)
                    connected.set()
                    finished.wait(timeout=WAIT_SECONDS * 2)
                return

        thread = threading.Thread(target=accept, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{listener.getsockname()[1]}/repo.git", connected
        finally:
            finished.set()
            thread.join(timeout=WAIT_SECONDS)


@pytest.mark.parametrize("owner_signal", [signal.SIGKILL, signal.SIGTERM])
def test_owner_death_stops_real_git_and_http_helpers(
    tmp_path: Path,
    stalled_git_endpoint: tuple[str, threading.Event],
    owner_signal: signal.Signals,
) -> None:
    url, connected = stalled_git_endpoint
    identities: list[ProcessIdentity] = []
    with subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", OWNER_SCRIPT, str(tmp_path / "mirror.git"), url],
        env=os.environ | {"DJANGO_SETTINGS_MODULE": "config.settings.test"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    ) as owner:
        try:
            assert connected.wait(timeout=WAIT_SECONDS), (
                "Git did not reach the endpoint."
            )
            identities = _descendants(owner.pid)
            assert len(identities) >= MIN_GIT_PROCESSES
            assert any("remote-http" in identity.command for identity in identities)
            os.kill(owner.pid, owner_signal)
            owner.wait(timeout=WAIT_SECONDS)
            _assert_stopped(identities)
        finally:
            _cleanup(owner, identities)


def test_supervisor_deadline_stops_real_git_and_http_helpers(
    tmp_path: Path, stalled_git_endpoint: tuple[str, threading.Event]
) -> None:
    url, connected = stalled_git_endpoint
    executable: str | None = shutil.which("git")
    assert executable is not None
    parent_read: int
    parent_write: int
    parent_read, parent_write = os.pipe()
    identities: list[ProcessIdentity] = []
    with (
        os.fdopen(parent_read, "rb") as reader,
        os.fdopen(parent_write, "wb"),
        subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                str(SUPERVISOR),
                "--parent-fd",
                str(parent_read),
                "--timeout",
                "2",
                "--",
                executable,
                "clone",
                "--mirror",
                "--",
                url,
                str(tmp_path / "mirror.git"),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=(parent_read,),
        ) as supervisor,
    ):
        reader.close()
        try:
            assert connected.wait(timeout=WAIT_SECONDS), (
                "Git did not reach the endpoint."
            )
            identities = _descendants(supervisor.pid)
            assert any("remote-http" in identity.command for identity in identities)
            assert supervisor.wait(timeout=WAIT_SECONDS) == TIMEOUT_EXIT_CODE
            _assert_stopped(identities)
        finally:
            _cleanup(supervisor, identities)


def test_exited_leader_cannot_leave_a_helper_that_ignores_term(tmp_path: Path) -> None:
    leader_script: Path = tmp_path / "leader.py"
    helper_script: Path = tmp_path / "helper.py"
    helper_pid: Path = tmp_path / "helper.pid"
    exit_trigger: Path = tmp_path / "exit"
    leader_script.write_text(LEADER_SCRIPT)
    helper_script.write_text(HELPER_SCRIPT)
    parent_read: int
    parent_write: int
    parent_read, parent_write = os.pipe()
    identities: list[ProcessIdentity] = []
    with (
        os.fdopen(parent_read, "rb") as reader,
        os.fdopen(parent_write, "wb"),
        subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                str(SUPERVISOR),
                "--parent-fd",
                str(parent_read),
                "--timeout",
                str(WAIT_SECONDS),
                "--",
                sys.executable,
                str(leader_script),
                str(helper_script),
                str(helper_pid),
                str(exit_trigger),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=(parent_read,),
        ) as supervisor,
    ):
        reader.close()
        try:
            deadline: float = time.monotonic() + WAIT_SECONDS
            while not helper_pid.exists() or not helper_pid.read_text():
                assert time.monotonic() < deadline, "The helper did not start."
                time.sleep(0.01)
            identity: ProcessIdentity | None = _identity(int(helper_pid.read_text()))
            assert identity is not None
            identities.append(identity)
            assert _running(identity)
            exit_trigger.touch()
            assert supervisor.wait(timeout=WAIT_SECONDS) == 0
            _assert_stopped(identities)
        finally:
            _cleanup(supervisor, identities)
