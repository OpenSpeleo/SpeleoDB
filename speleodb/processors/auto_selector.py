from django.core.exceptions import ValidationError

from speleodb.processors._impl.ariane import AGRFileProcessor
from speleodb.processors._impl.ariane import TMLFileProcessor
from speleodb.processors._impl.ariane import TMLUFileProcessor
from speleodb.processors._impl.compass import DATFileProcessor
from speleodb.processors._impl.compass import MAKFileProcessor
from speleodb.processors._impl.misc import DumpProcessor
from speleodb.processors.base import Artifact
from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Format
from speleodb.surveys.models import Project


class AutoSelector:
    @staticmethod
    def get_processor(fileformat: Format.FileFormat, f_extension=None):
        match fileformat:
            case Format.FileFormat.ARIANE_TML:
                return TMLFileProcessor

            case Format.FileFormat.ARIANE_TMLU:
                return TMLUFileProcessor

            case Format.FileFormat.ARIANE_AGR:
                return AGRFileProcessor

            case Format.FileFormat.COMPASS_DAT:
                return DATFileProcessor

            case Format.FileFormat.COMPASS_MAK:
                return MAKFileProcessor

            case Format.FileFormat.AUTO:
                if f_extension is None:
                    raise ValueError("Automatic Processor discovery not enabled.")

                for candidate_cls in BaseFileProcessor.__subclasses__():
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
        fileformat: Format.FileFormat, project: Project, hexsha: str
    ):
        processor_cls = AutoSelector.get_processor(fileformat=fileformat)

        return processor_cls(project=project, hexsha=hexsha)
