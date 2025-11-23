# -*- coding: utf-8 -*-


from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from speleodb.git_engine.core import GitCommit
from speleodb.git_engine.core import GitFile
from speleodb.processors._impl.compass_toml import CompassConfig
from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import FileFormat
from speleodb.utils.timing_ctx import timed_section

if TYPE_CHECKING:
    from speleodb.processors.artifact import Artifact


class CompassZIPFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [".czip"]
    ALLOWED_MIMETYPES = ["application/octet-stream", "application/zip", "text/plain"]
    ASSOC_FILEFORMAT = FileFormat.COMPASS_ZIP

    TARGET_FOLDER = None
    TARGET_SAVE_FILENAME = "project.zip"
    TARGET_DOWNLOAD_FILENAME = "{project_name}__{timestamp}.zip"

    def _generate_or_copy_file_for_download(
        self, commit: GitCommit, target_f: Path
    ) -> None:
        gitfile: GitFile
        for item in commit.tree.traverse():
            if not isinstance(item, GitFile):
                continue

            if item.path.name == CompassConfig.__FILENAME__:
                gitfile = item
                break

        else:
            raise FileNotFoundError(
                f"Impossible to find `{CompassConfig.__FILENAME__}` at commit: "
                f"`{commit.hexsha}`."
            )

        compass_cfg = CompassConfig.from_toml(gitfile.content)

        with zipfile.ZipFile(target_f, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            commit_files: list[GitFile] = [
                item
                for item in commit.tree.traverse()
                if isinstance(item, GitFile) and str(item.path) in compass_cfg.files
            ]

            if not commit_files:
                raise RuntimeError(f"No file found in commit: `{commit.hexsha}`")

            if len(commit_files) != len(compass_cfg.files):
                missing_files = compass_cfg.files - {str(f.path) for f in commit_files}
                raise RuntimeError(
                    f"Some files listed in `{CompassConfig.__FILENAME__}` are missing "
                    f"in commit `{commit.hexsha}`: {missing_files}"
                )

            for file in commit_files:
                zipf.writestr(
                    str(file.path),
                    file.content.getvalue(),
                )

    def _add_to_project(self, artifact: Artifact) -> list[Path]:
        with TemporaryDirectory() as tmp_dir:
            tmp_dir_path = Path(tmp_dir)

            with timed_section("File DMP pre-processing"):
                input_f = tmp_dir_path / "input.zip"
                artifact.write(input_f)

                unzip_folder = tmp_dir_path / "extracted"
                unzip_folder.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(input_f, mode="r") as zip_ref:
                    # Extract all files, creating directories as needed
                    zip_ref.extractall(unzip_folder)

            with timed_section("Decode `compass.toml` and prepare files"):
                compass_toml_path = unzip_folder / CompassConfig.__FILENAME__
                if not compass_toml_path.is_file():
                    raise FileNotFoundError(
                        "`compass.toml` not found in the provided ZIP file."
                    )

                compass_cfg = CompassConfig.from_toml(compass_toml_path)

                stored_files = [
                    p
                    for p in unzip_folder.rglob("*")
                    if p.is_file()
                    # Essential to remove files created by macOS Finder
                    and not (p.name.startswith("._") or "__MACOSX" in str(p.parts))
                ]

                for file in stored_files:
                    relative_path = file.relative_to(unzip_folder)
                    if str(relative_path) not in compass_cfg.files:
                        raise ValueError(
                            f"File `{relative_path}` found in ZIP but not listed in "
                            f"`{CompassConfig.__FILENAME__}`."
                        )

            copied_files: list[Path] = []
            with timed_section("File copy to project dir"):
                for file in stored_files:
                    target_path = self.storage_folder / file.relative_to(unzip_folder)
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(file, target_path)
                    copied_files.append(target_path)

        return copied_files


class CompassManualFileProcessor(BaseFileProcessor):
    ALLOWED_FULLNAMES = ["compass.toml"]
    ALLOWED_EXTENSIONS = [".dat", ".mak", ".plt"]
    ALLOWED_MIMETYPES = ["application/octet-stream", "text/plain"]
    ASSOC_FILEFORMAT = FileFormat.COMPASS_MANUAL

    TARGET_FOLDER = None
    TARGET_SAVE_FILENAME = None
    TARGET_DOWNLOAD_FILENAME = None
