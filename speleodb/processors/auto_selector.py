# -*- coding: utf-8 -*-

from __future__ import annotations

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile

from speleodb.processors._impl.ariane import ArianeAGRFileProcessor
from speleodb.processors._impl.ariane import ArianeTMLFileProcessor
from speleodb.processors._impl.ariane import ArianeTMLUFileProcessor
from speleodb.processors._impl.compass import CompassManualFileProcessor
from speleodb.processors._impl.compass import CompassZIPFileProcessor
from speleodb.processors._impl.dump import DumpProcessor
from speleodb.processors.artifact import Artifact
from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import Project
from speleodb.utils.timing_ctx import timed_section


class AutoSelector:
    @staticmethod
    def get_processor(
        fileformat: FileFormat, artifact: Artifact | None = None
    ) -> type[BaseFileProcessor]:
        match fileformat:
            case FileFormat.ARIANE_TML:
                return ArianeTMLFileProcessor

            case FileFormat.ARIANE_TMLU:
                return ArianeTMLUFileProcessor

            case FileFormat.ARIANE_AGR:
                return ArianeAGRFileProcessor

            case FileFormat.COMPASS_ZIP:
                return CompassZIPFileProcessor

            case FileFormat.COMPASS_MANUAL:
                return CompassManualFileProcessor

            case FileFormat.AUTO:
                if artifact is None:
                    raise ValueError("Automatic Processor discovery not enabled.")

                for candidate_cls in BaseFileProcessor.__subclasses__():
                    try:
                        if artifact.name in candidate_cls.ALLOWED_FULLNAMES:
                            return candidate_cls

                        if artifact.extension in candidate_cls.ALLOWED_EXTENSIONS:
                            return candidate_cls

                    except TypeError:  # Only allows downloads
                        continue

                # if no known processor is matching
                return BaseFileProcessor

            case FileFormat.DUMP:
                return DumpProcessor

            case _:
                return BaseFileProcessor

    @staticmethod
    def get_upload_processor(
        fileformat: FileFormat,
        file: InMemoryUploadedFile | TemporaryUploadedFile,
        project: Project,
    ) -> BaseFileProcessor:
        if not isinstance(file, (InMemoryUploadedFile, TemporaryUploadedFile)):
            raise TypeError(f"Unexpected object type received: {type(file)}")

        if not isinstance(fileformat, FileFormat):
            raise TypeError(
                f"Unknown `fileformat` received, expected one of {FileFormat.choices}"
            )

        with timed_section("Get Processor - Func"):
            artifact = Artifact(file)
            processor_cls = AutoSelector.get_processor(
                fileformat=fileformat,
                artifact=artifact,
            )

        with timed_section("Get Processor - Instanciation"):
            return processor_cls(project=project)

    @staticmethod
    def get_download_processor(
        fileformat: FileFormat, project: Project, hexsha: str | None
    ) -> BaseFileProcessor:
        with timed_section("Get Processor - Func"):
            processor_cls = AutoSelector.get_processor(fileformat=fileformat)

        with timed_section("Get Processor - Instanciation"):
            return processor_cls(project=project)
