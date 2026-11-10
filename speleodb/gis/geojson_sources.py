"""Materialize one immutable Git revision for upload jobs and history rebuilds."""

from __future__ import annotations

import logging
import tomllib
from typing import TYPE_CHECKING

from speleodb.common.constants import ARIANE_TML_FILENAME
from speleodb.common.constants import COMPASS_TOML_FILENAME
from speleodb.common.constants import STALAGMIGHT_FILENAME
from speleodb.common.enums import ProjectType
from speleodb.git_engine.core import GitFile

if TYPE_CHECKING:
    from pathlib import Path

    from speleodb.git_engine.core import GitCommit
    from speleodb.surveys.models import Project

logger = logging.getLogger(__name__)


def materialize_geojson_source(
    project: Project, commit: GitCommit, directory: Path
) -> Path | None:
    """Read blobs at the supplied SHA; never check out or mutate shared Git state."""
    single_file_sources: dict[str, str] = {
        ProjectType.ARIANE: ARIANE_TML_FILENAME,
        ProjectType.STALAGMIGHT: STALAGMIGHT_FILENAME,
    }
    if filename := single_file_sources.get(project.type):
        try:
            source = commit.tree / filename
        except KeyError:
            return None
        destination = directory / filename
        with destination.open("wb") as output:
            source.blob.stream_data(output)
        return destination

    if project.type != ProjectType.COMPASS:
        return None
    files = {
        str(item.path): item
        for item in commit.tree.traverse()
        if isinstance(item, GitFile)
    }
    config_file = files.get(COMPASS_TOML_FILENAME)
    if config_file is None:
        return None
    config_path = directory / COMPASS_TOML_FILENAME
    with config_path.open("wb") as output:
        config_file.blob.stream_data(output)
    # Only the source paths are needed here. Keep model initialization
    # independent of the upload processor package and its auto-discovery.
    with config_path.open("rb") as source_config:
        project_files = tomllib.load(source_config)["project"]
    mak_file: str = project_files["mak_file"]
    source_paths = {
        COMPASS_TOML_FILENAME,
        mak_file,
        *project_files["dat_files"],
        *(project_files.get("plt_files") or []),
    }
    root = directory.resolve()
    for relative_path in source_paths:
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
        with destination.open("wb") as output:
            source.blob.stream_data(output)
    return directory / mak_file
