import zipfile
from pathlib import Path

from git.exc import GitCommandError

from speleodb.git_engine.core import GitFile
from speleodb.git_engine.exceptions import GitBaseError
from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Format


class DumpProcessor(BaseFileProcessor):
    TARGET_DOWNLOAD_FILENAME = "{project_name}__{timestamp}.zip"
    ASSOC_FILEFORMAT = Format.FileFormat.DUMP

    def _generate_or_copy_file_for_download(self, target_f: Path) -> None:
        with zipfile.ZipFile(target_f, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            try:
                try:
                    commit = self.project.git_repo.commit(self.hexsha)
                except ValueError:  # In case the commit doesn't exist - pull and retry
                    self.project.git_repo.pull()
                    commit = self.project.git_repo.commit(self.hexsha)

                if commit is None:
                    raise ValueError  # noqa: TRY301

            except (ValueError, GitBaseError, GitCommandError) as e:
                raise RuntimeError(f"Impossible to find commit: `{self.hexsha}`") from e

            commit_files = [
                item for item in commit.tree.traverse() if isinstance(item, GitFile)
            ]

            if not commit_files:
                raise RuntimeError(f"No file found in commit: `{self.hexsha}`")

            for file in commit_files:
                zipf.writestr(
                    str(file.path),
                    file.content.getvalue(),
                )
