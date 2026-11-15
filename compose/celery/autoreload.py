"""Reload local Celery services after Python edits and a complete warm shutdown."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING

from watchfiles import Change
from watchfiles import DefaultFilter
from watchfiles import watch

if TYPE_CHECKING:
    from types import FrameType

logger = logging.getLogger(__name__)
SOURCE_FILTER = DefaultFilter(
    ignore_dirs=(*DefaultFilter.ignore_dirs, "tests", "test", ".workdir", ".artifacts")
)


def source_paths(app_root: Path, python_path: str) -> tuple[Path, ...]:
    """Watch application packages and the source packages in Python overlays."""
    roots: set[Path] = {
        app_root / name
        for name in (
            "config",
            "speleodb",
            "frontend_private",
            "frontend_public",
            "frontend_errors",
            "well_known",
            "compose/celery",
        )
        if (app_root / name).is_dir()
    }
    for entry in python_path.split(os.pathsep):
        path: Path = Path(entry).resolve()
        if not entry or path == app_root.resolve() or not path.is_dir():
            continue
        roots.update(
            package
            for package in path.iterdir()
            if package.is_dir()
            and (package / "__init__.py").is_file()
            and SOURCE_FILTER(Change.modified, str(package / "__init__.py"))
        )
    return tuple(sorted(roots))


def source_changed(change: Change, path: str) -> bool:
    name: str = Path(path).name
    return (
        name.endswith(".py")
        and not name.startswith("test_")
        and name != "conftest.py"
        and SOURCE_FILTER(change, path)
    )


def run(command: list[str], paths: tuple[Path, ...]) -> int:
    stopped: Event = Event()

    def stop(signum: int, frame: FrameType | None) -> None:
        stopped.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logger.info("Watching Python sources: %s", ", ".join(map(str, paths)))
    with closing(
        watch(
            *paths,
            watch_filter=source_changed,
            stop_event=stopped,
            rust_timeout=1000,
            yield_on_timeout=True,
        )
    ) as changes:
        # Initialize the native watcher before starting the service, so imports
        # and edits during startup cannot fall into an unwatched interval.
        next(changes, None)
        while not stopped.is_set():
            with subprocess.Popen(command, start_new_session=True) as process:  # noqa: S603
                try:
                    for changed in changes:
                        exit_code: int | None = process.poll()
                        if exit_code is not None:
                            return exit_code
                        if changed:
                            logger.info(
                                "Python source changed; waiting for warm shutdown"
                            )
                            break
                finally:
                    if process.poll() is None:
                        # Celery's prefork children ignore SIGINT; the worker
                        # finishes active tasks and joins its pool. Beat handles
                        # SIGINT synchronously and releases its scheduler lease.
                        # Wait before replacement, with no code-reload kill timer.
                        os.killpg(process.pid, signal.SIGINT)
                    process.wait()
    return 0


def main() -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=("worker", "beat"))
    args: argparse.Namespace = parser.parse_args()
    app_root: Path = Path(__file__).resolve().parents[2]
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return run(
        ["/bin/bash", str(app_root / "compose/celery" / args.service / "start")],
        source_paths(app_root, os.environ.get("PYTHONPATH", "")),
    )


if __name__ == "__main__":
    sys.exit(main())
