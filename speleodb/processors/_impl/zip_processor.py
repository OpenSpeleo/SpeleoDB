import zipfile
from pathlib import Path

from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Format


class DumpProcessor(BaseFileProcessor):
    TARGET_DOWNLOAD_FILENAME = "project_{timestamp}.zip"
    ASSOC_FILEFORMAT = Format.FileFormat.DUMP

    def postprocess_file_before_download(self, filepath: Path):
        with zipfile.ZipFile(filepath, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            for file in self.project.git_repo.path.glob("*"):
                if not file.is_file() or file.name.startswith("."):
                    continue

                zipf.write(file, file.relative_to(self.project.git_repo.path))

        return filepath
