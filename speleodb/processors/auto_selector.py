from django.core.exceptions import ValidationError

from speleodb.processors._impl.ariane_processor import TMLFileProcessor
from speleodb.processors._impl.ariane_processor import TMLUFileProcessor
from speleodb.processors._impl.zip_processor import DumpProcessor
from speleodb.processors.base import Artifact
from speleodb.surveys.models import Format
from speleodb.surveys.models import Project

CANDIDATE_PROCESSORS = [TMLFileProcessor, TMLUFileProcessor]


class AutoSelector:
    @staticmethod
    def get_processor(fileformat: Format.FileFormat, f_extension=None):
        match fileformat:
            case Format.FileFormat.ARIANE_TML:
                return TMLFileProcessor

            case Format.FileFormat.ARIANE_TMLU:
                return TMLUFileProcessor

            case Format.FileFormat.AUTO:
                if f_extension is None:
                    raise ValueError("Automatic Processor discovery not enabled.")

                for candidate_cls in CANDIDATE_PROCESSORS:
                    if f_extension in candidate_cls.ALLOWED_EXTENSIONS:
                        return candidate_cls

            case Format.FileFormat.DUMP:
                return DumpProcessor

        raise ValidationError(
            f"This file format `{fileformat}` [with extension: `{f_extension}`] is not "
            "implemented yet ..."
        )

    @staticmethod
    def get_upload_processor(fileformat: Format.FileFormat, file, project: Project):
        if not isinstance(fileformat, Format.FileFormat):
            raise TypeError(
                "Unknown `fileformat` received, expected one of "
                f"{Format.FileFormat.choices}"
            )

        file = Artifact(file)
        processor_cls = AutoSelector.get_processor(
            fileformat=fileformat, f_extension=file.extension
        )
        return processor_cls(project=project)

    @staticmethod
    def get_download_processor(
        fileformat: Format.FileFormat, project: Project, commit_sha1: str
    ):
        processor_cls = AutoSelector.get_processor(fileformat=fileformat)

        return processor_cls(project=project, commit_sha1=commit_sha1)
