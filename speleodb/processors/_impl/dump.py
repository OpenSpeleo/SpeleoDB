import zipfile
from pathlib import Path

from speleodb.git_engine.core import GitCommit
from speleodb.git_engine.core import GitFile
from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Format


class DumpProcessor(BaseFileProcessor):
    TARGET_DOWNLOAD_FILENAME = "{project_name}__{timestamp}.zip"
    ASSOC_FILEFORMAT = Format.FileFormat.DUMP

    def _generate_or_copy_file_for_download(
        self, commit: GitCommit, target_f: Path
    ) -> None:
        if not isinstance(commit, GitCommit):
            raise TypeError(f"Unexpected type for `commit`: {type(commit)}.")

        with zipfile.ZipFile(target_f, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            commit_files: list[GitFile] = [
                item  # type: ignore[misc]
                for item in commit.tree.traverse()
                if isinstance(item, GitFile)
            ]

            if not commit_files:
                raise RuntimeError(f"No file found in commit: `{commit.hexsha}`")

            for file in commit_files:
                zipf.writestr(
                    str(file.path),
                    file.content.getvalue(),
                )
