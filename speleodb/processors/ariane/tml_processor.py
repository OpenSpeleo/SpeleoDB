import zipfile
from pathlib import Path

from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Project
from speleodb.users.models import User


class TMLFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [".tml"]
    ALLOWED_MIMETYPE = ["application/octet-stream", "application/zip"]
    TARGET_SAVE_FILENAME = "Data.xml"
    TARGET_DOWNLOAD_FILENAME = "project_{timestamp}.tml"

    def preprocess_file_before_upload(self, user: User, project: Project):
        with zipfile.ZipFile(self.file) as zip_archive:
            return zip_archive.read(self.TARGET_SAVE_FILENAME)

    @classmethod
    def postprocess_file_before_download(cls, filepath: Path, project: Project):
        with zipfile.ZipFile(filepath, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            for file in project.git_repo.path.glob("*"):
                if not file.is_file() or file.name.startswith("."):
                    continue

                zipf.write(file, file.relative_to(project.git_repo.path))

        return filepath
