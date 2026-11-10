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
    filename: str | None
    match project.type:
        case ProjectType.ARIANE:
            filename = ARIANE_TML_FILENAME
        case ProjectType.STALAGMIGHT:
            filename = STALAGMIGHT_FILENAME
        case ProjectType.COMPASS:
            filename = None
        case _:
            return None
    if filename is not None:
        try:
            source = commit.tree / filename
        except KeyError:
            return None
        destination = directory / filename
        with destination.open("wb") as output:
            source.blob.stream_data(output)
        return destination

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
        project_files = tomllib.load(source_config).get("project")
    if not isinstance(project_files, dict):
        raise TypeError("The Compass project table is required.")
    mak_file = project_files.get("mak_file")
    if not isinstance(mak_file, str):
        raise TypeError("Compass mak_file must be a string.")
    dat_files = project_files.get("dat_files")
    if not isinstance(dat_files, list) or not all(
        isinstance(path, str) for path in dat_files
    ):
        raise TypeError("Compass dat_files must be a list of strings.")
    plt_files = project_files.get("plt_files", [])
    if not isinstance(plt_files, list) or not all(
        isinstance(path, str) for path in plt_files
    ):
        raise TypeError("Compass plt_files must be a list of strings.")
    source_paths = {
        COMPASS_TOML_FILENAME,
        mak_file,
        *dat_files,
        *plt_files,
    }
    root = directory.resolve()
    for relative_path in source_paths:
        if not (directory / relative_path).resolve().is_relative_to(root):
            raise ValueError("A Compass source path escapes its temporary directory.")
    for relative_path in source_paths:
        source = files.get(relative_path)
        if source is None:
            logger.warning(
                "Missing Compass file %s in commit %s", relative_path, commit.hexsha
            )
            return None
        destination = directory / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as output:
            source.blob.stream_data(output)
    return directory / mak_file
