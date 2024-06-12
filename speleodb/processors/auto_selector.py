from pathlib import Path

from django.core.exceptions import ValidationError

from speleodb.processors.ariane.tml_processor import TMLFileProcessor
from speleodb.processors.ariane.tmlu_processor import TMLUFileProcessor
from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Project

CANDIDATE_PROCESSORS = [TMLFileProcessor, TMLUFileProcessor]


def AutoSelectorUploadFileProcessor(file):  # noqa: N802
    file_ext = Path(file.name).suffix.lower()

    for processor_cls in CANDIDATE_PROCESSORS:
        if file_ext in processor_cls.ALLOWED_EXTENSIONS:
            return processor_cls(file=file)

    raise ValidationError(f"No valid file processor found for extension: {file_ext}")


def AutoSelectorDownloadFileProcessor(project: Project, commit_sha1: str):  # noqa: N802
    BaseFileProcessor.checkout_commit_or_master(
        project=project, commit_sha1=commit_sha1
    )

    git_repo_path = project.git_repo.path

    for processor_cls in CANDIDATE_PROCESSORS:
        if (git_repo_path / processor_cls.TARGET_SAVE_FILENAME).is_file():
            return processor_cls.prepare_file_for_download(
                project=project, commit_sha1=commit_sha1
            )

    raise ValidationError(f"No valid file processor found for project: {project.name}")
