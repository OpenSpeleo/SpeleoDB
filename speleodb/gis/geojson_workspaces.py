"""Private disk workspaces with cleanup after normal exits and lost workers."""

from __future__ import annotations

import fcntl
import logging
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)
WORKSPACE_PREFIX = "work-"
LOCK_FILENAME = ".active"


def cleanup_geojson_workspaces() -> None:
    """Sweep this worker's abandoned work; kernel locks protect live processes."""
    root = Path(settings.GEOJSON_GENERATION_SCRATCH_DIR)
    if not root.is_dir():
        return
    cutoff = (
        timezone.now().timestamp() - settings.GEOJSON_GENERATION_CLEANUP_GRACE_SECONDS
    )
    for directory in root.glob(f"{WORKSPACE_PREFIX}*"):
        try:
            if (
                directory.is_symlink()
                or not directory.is_dir()
                or directory.stat().st_mtime > cutoff
            ):
                continue
            # A process can die between mkdir and opening the marker. Creating
            # it here also permits recovery of that empty abandoned directory.
            descriptor = os.open(
                directory / LOCK_FILENAME,
                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
                0o600,
            )
            with os.fdopen(descriptor, "rb") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                shutil.rmtree(directory)
        except FileNotFoundError:
            # The owner or another sweeper already removed it.
            continue
        except OSError:
            logger.warning("Unable to clean abandoned GeoJSON workspace %s", directory)


@contextmanager
def geojson_workspace(*, prefix: str) -> Iterator[Path]:
    """Own the clone, extracted sources and authentication files as one scope."""
    root = Path(settings.GEOJSON_GENERATION_SCRATCH_DIR)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    cleanup_geojson_workspaces()
    with TemporaryDirectory(
        prefix=f"{WORKSPACE_PREFIX}{prefix}", dir=root
    ) as temporary:
        directory = Path(temporary)
        with (directory / LOCK_FILENAME).open("xb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield directory
