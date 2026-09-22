"""Materialize one immutable Git revision for upload jobs and history rebuilds."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from speleodb.common.enums import ProjectType
from speleodb.git_engine.core import GitFile
from speleodb.processors import ArianeTMLFileProcessor
from speleodb.processors._impl.compass_toml import CompassTOML
from speleodb.processors._impl.compass_toml import get_compass_mak_filepath

if TYPE_CHECKING:
    from pathlib import Path

    from speleodb.git_engine.core import GitCommit
    from speleodb.surveys.models import Project

logger = logging.getLogger(__name__)


def materialize_geojson_source(
    project: Project, commit: GitCommit, directory: Path
) -> Path | None:
    """Read blobs at the supplied SHA; never check out or mutate shared Git state."""
    if project.type == ProjectType.ARIANE:
        filename = ArianeTMLFileProcessor.TARGET_SAVE_FILENAME
        try:
            source = commit.tree / filename
        except KeyError:
            return None
        destination = directory / filename
        destination.write_bytes(source.content.getvalue())
        return destination

    if project.type != ProjectType.COMPASS:
        return None
    files = {
        str(item.path): item
        for item in commit.tree.traverse()
        if isinstance(item, GitFile)
    }
    config_file = files.get(CompassTOML.__FILENAME__)
    if config_file is None:
        return None
    config = CompassTOML.from_toml(config_file.content)
    root = directory.resolve()
    for relative_path in config.files:
        source = files.get(relative_path)
        if source is None:
            logger.warning(
                "Missing Compass file %s in commit %s", relative_path, commit.hexsha
            )
            return None
        destination = directory / relative_path
        if not destination.resolve().is_relative_to(root):
            raise ValueError("A Compass source path escapes its temporary directory.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.content.getvalue())
    return get_compass_mak_filepath(directory)
