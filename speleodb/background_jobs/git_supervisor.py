"""Contain Git helpers even when the export task is killed without cleanup.

This standalone stdlib process owns Git's process group. Its parent holds the
only write end of a liveness pipe; EOF therefore survives SIGKILL and does not
depend on Python signal handlers running in the Celery child.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import selectors
import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import FrameType


POLL_SECONDS: float = 0.1
TERMINATE_SECONDS: int = 5
TIMEOUT_EXIT_CODE: int = 124
STOPPED_EXIT_CODE: int = 125


def _terminate_group(process: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=TERMINATE_SECONDS)
    except subprocess.TimeoutExpired:
        pass
    finally:
        # The leader can exit before a helper does. Always signal its group,
        # including when wait() above succeeds immediately.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def supervise(*, parent_fd: int, timeout: float, command: list[str]) -> int:
    stopping: bool = False

    def stop(signum: int, frame: FrameType | None) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    deadline: float = time.monotonic() + timeout
    with selectors.DefaultSelector() as selector:
        selector.register(parent_fd, selectors.EVENT_READ)
        with subprocess.Popen(  # noqa: S603
            command,
            start_new_session=True,
            close_fds=True,
        ) as process:
            try:
                while True:
                    returncode: int | None = process.poll()
                    if returncode is not None:
                        return returncode if returncode >= 0 else 128 - returncode
                    if stopping:
                        return STOPPED_EXIT_CODE
                    remaining: float = deadline - time.monotonic()
                    if remaining <= 0:
                        return TIMEOUT_EXIT_CODE
                    if selector.select(timeout=min(POLL_SECONDS, remaining)):
                        if not os.read(parent_fd, 1):
                            return STOPPED_EXIT_CODE
            finally:
                _terminate_group(process)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-fd", type=int, required=True)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments: argparse.Namespace = parser.parse_args()
    command: list[str] = arguments.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command or arguments.timeout <= 0:
        parser.error("A command and positive timeout are required.")
    try:
        return supervise(
            parent_fd=arguments.parent_fd,
            timeout=arguments.timeout,
            command=command,
        )
    finally:
        os.close(arguments.parent_fd)


if __name__ == "__main__":
    sys.exit(main())
