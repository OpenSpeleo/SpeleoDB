import shutil
from pathlib import Path

from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Project


class TMLUFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [".tmlu"]
    ALLOWED_MIMETYPE = ["application/octet-stream"]
    TARGET_SAVE_FILENAME = "project.tmlu"
    TARGET_DOWNLOAD_FILENAME = "project_{timestamp}.tmlu"

    @classmethod
    def postprocess_file_before_download(cls, filepath: Path, project: Project):
        shutil.copy(
            src=Path(project.git_repo.path) / cls.TARGET_SAVE_FILENAME, dst=filepath
        )

        return filepath
