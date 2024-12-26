from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile

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
from speleodb.utils.timing_ctx import timed_section


class AutoSelector:
    @staticmethod
    def get_processor(
        fileformat: Format.FileFormat, f_extension: str | None = None
    ) -> type[BaseFileProcessor]:
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
                    try:
                        if f_extension in candidate_cls.ALLOWED_EXTENSIONS:
                            return candidate_cls
                    except TypeError:  # Only allows downloads
                        continue

            case Format.FileFormat.DUMP:
                return DumpProcessor

        return BaseFileProcessor

    @staticmethod
    def get_upload_processor(
        fileformat: Format.FileFormat,
        file: InMemoryUploadedFile | TemporaryUploadedFile,
        project: Project,
    ) -> type[BaseFileProcessor]:
        if not isinstance(file, (InMemoryUploadedFile, TemporaryUploadedFile)):
            raise TypeError(f"Unexpected object type received: {type(file)}")

        if not isinstance(fileformat, Format.FileFormat):
            raise TypeError(
                "Unknown `fileformat` received, expected one of "
                f"{Format.FileFormat.choices}"
            )

        with timed_section("Get Processor - Func"):
            file = Artifact(file)
            processor_cls = AutoSelector.get_processor(
                fileformat=fileformat, f_extension=file.extension
            )
        with timed_section("Get Processor - Instanciation"):
            return processor_cls(project=project)

    @staticmethod
    def get_download_processor(
        fileformat: Format.FileFormat, project: Project
    ) -> type[BaseFileProcessor]:
        processor_cls = AutoSelector.get_processor(fileformat=fileformat)

        return processor_cls(project=project)
