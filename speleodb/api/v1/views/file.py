#!/usr/bin/env python
# -*- coding: utf-8 -*-

import contextlib
import logging
import pathlib
import tempfile
from collections import defaultdict

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.http import Http404
from git.exc import GitCommandError
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.permissions import UserHasWriteAccess
from speleodb.api.v1.permissions import UserOwnsProjectMutex
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.serializers import UploadSerializer
from speleodb.git_engine.exceptions import GitBlobNotFoundError
from speleodb.git_engine.gitlab_manager import GitlabError
from speleodb.processors.auto_selector import AutoSelector
from speleodb.surveys.models import Format
from speleodb.surveys.models import Project
from speleodb.utils.exceptions import ProjectNotFound
from speleodb.utils.response import DownloadResponseFromBlob
from speleodb.utils.response import DownloadResponseFromFile
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse
from speleodb.utils.timing_ctx import timed_section

logger = logging.getLogger(__name__)


class FileUploadView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [UserHasWriteAccess, UserOwnsProjectMutex]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def put(self, request, fileformat: Format.FileFormat, *args, **kwargs):  # noqa: PLR0915
        with timed_section("Project Upload"):
            # ~~~~~~~~~~~~~~~~~~~~~~ START of URL Validation ~~~~~~~~~~~~~~~~~~~~ #
            with timed_section("URL Validation"):
                try:
                    fileformat = getattr(Format.FileFormat, fileformat.upper())
                except AttributeError:
                    return ErrorResponse(
                        {
                            "error": (
                                "The file format requested is not recognized: "
                                f"{fileformat}"
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if fileformat.label.lower() not in Format.FileFormat.upload_choices:
                    msg = f"The format: {fileformat} is not supported for upload"
                    logger.exception(
                        f"{msg}, expected: {Format.FileFormat.upload_choices}"
                    )
                    return ErrorResponse(
                        {"error": msg},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # ~~~~~~~~~~~~~~~~~~~~~~~ END of URL Validation ~~~~~~~~~~~~~~~~~~~~~ #

            # ~~~~~~~~~~~~~~~~~~ START of Form Data Validation ~~~~~~~~~~~~~~~~~~ #
            with timed_section("Form Data Validation"):
                try:
                    files = request.FILES.getlist("artifact")
                except KeyError:
                    return ErrorResponse(
                        {"error": "Uploaded file(s) `artifact` is/are missing."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                commit_message = request.data.get("message", None)

                # Verify the commit message is not empty
                if commit_message is None or commit_message == "":
                    data = {
                        "error": (
                            f"Empty or no `message` received: `{commit_message}`."
                        )
                    }
                    return ErrorResponse(data, status=status.HTTP_400_BAD_REQUEST)

                # Verify there's at least one file
                if not files:
                    return ErrorResponse(
                        {"error": "No files uploaded"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Verify there's a maximum of `DJANGO_UPLOAD_TOTAL_FILES_LIMIT` files
                # uploaded in one API call.
                if len(files) > settings.DJANGO_UPLOAD_TOTAL_FILES_LIMIT:
                    return ErrorResponse(
                        {
                            "error": (
                                f"Too many files uploaded. Received {len(files)} "
                                "files, maximum number of files allowed: "
                                f"{settings.DJANGO_UPLOAD_TOTAL_FILES_LIMIT}."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Verify the total size and each individual file size doesn't exceed the
                # global limit
                total_filesize = 0
                for file in files:
                    total_filesize += file.size
                    # Check if file size exceeds globally set limit
                    if (
                        file.size
                        > settings.DJANGO_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT
                        * 1024
                        * 1024
                    ):
                        return ErrorResponse(
                            {
                                "error": (
                                    f"The file size for `{file.name}` "
                                    f"[{file.size / 1024. /1204. } Mb], exceeds the limit: "  # noqa: E501
                                    f"{settings.DJANGO_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT} Mb"  # noqa: E501
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    # Check file type
                    if not isinstance(
                        file, (InMemoryUploadedFile, TemporaryUploadedFile)
                    ):
                        return ErrorResponse(
                            {"error": f"Unknown artifact received: `{file.name}`"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                if (
                    total_filesize
                    > settings.DJANGO_UPLOAD_TOTAL_FILES_LIMIT * 1024 * 1204
                ):
                    return ErrorResponse(
                        {
                            "error": (
                                f"The total file size submitted: "
                                f"[{file.size / 1024. /1204. } Mb], exceeds the limit: "
                                f"{settings.DJANGO_UPLOAD_TOTAL_FILES_LIMIT} Mb"
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # ~~~~~~~~~~~~~~~~~~~~ END of Form Data Validation ~~~~~~~~~~~~~~~~~~~~ #

            # ~~~~~~~~~~~~~~~~~ START of writing files to project ~~~~~~~~~~~~~~~~~ #
            with timed_section("Git Project - Checkout and Pull"):
                project: Project = self.get_object()
                # Make sure the project is update to ToT (Top of Tree)
                project.git_repo.checkout_default_branch()

            with timed_section("Project Edition - File Adding - Git Commit & Push"):
                project: Project = self.get_object()

                format_assoc = defaultdict(lambda: False)
                uploaded_files = []
                try:
                    for file in files:
                        with timed_section(f"File Adding: `{file.name}`"):
                            # maximum retry attempts in case of Git exception
                            with timed_section("Get Upload Processor"):
                                git_error = None
                                for _ in range(5):
                                    try:
                                        processor = AutoSelector.get_upload_processor(
                                            fileformat=fileformat,
                                            file=file,
                                            project=project,
                                        )
                                        break
                                    except GitCommandError as e:
                                        git_error = str(e)
                                else:
                                    return ErrorResponse(
                                        f"Git Error: {git_error}",
                                        status=status.HTTP_400_BAD_REQUEST,
                                    )

                            with timed_section("File Management"):
                                if fileformat == Format.FileFormat.AUTO:
                                    fileformat = processor.ASSOC_FILEFORMAT

                                # Associates the project with the format, ignore if
                                # already done. We have to start with this in order to
                                # have: `commit_date` > creation_date.
                                f_obj, created = Format.objects.get_or_create(
                                    project=project, _format=fileformat
                                )
                                format_assoc[f_obj] = format_assoc[f_obj] or created

                                with timed_section("File copy to project"):
                                    uploaded_file = processor.add_file_to_project(
                                        file=file
                                    )
                                    uploaded_files.append(uploaded_file)

                    with timed_section(f"GIT Commit and Push: `{file.name}`"):
                        # Finally commit the project - None if project not dirty
                        hexsha: str | None = project.commit_and_push_project(
                            message=commit_message, author=request.user
                        )

                    with timed_section("HTTP Response Construction"):
                        # Refresh the `modified_date` field
                        project.save()

                        return SuccessResponse(
                            {
                                "files": [
                                    str(f.path.relative_to(project.git_repo_dir))
                                    for f in uploaded_files
                                ],
                                "content_types": [
                                    f.content_type for f in uploaded_files
                                ],
                                "message": commit_message,
                                "hexsha": hexsha,
                                "project": ProjectSerializer(
                                    project, context={"user": request.user}
                                ).data,
                            }
                        )

                except (ValidationError, FileNotFoundError) as e:
                    for f_obj, created in format_assoc.items():
                        if created:
                            f_obj.delete()
                    return ErrorResponse(
                        {"error": e}, status=status.HTTP_400_BAD_REQUEST
                    )

                except GitlabError as e:
                    for f_obj, created in format_assoc.items():
                        if created:
                            f_obj.delete()
                    return ErrorResponse(
                        {"error": f"There has been a problem accessing gitlab: `{e}`"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                except Exception as e:  # noqa: BLE001
                    for f_obj, created in format_assoc.items():
                        if created:
                            f_obj.delete()
                    return ErrorResponse(
                        {"error": f"There has been a problem committing the file: {e}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )


class FileDownloadView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [UserHasReadAccess]
    serializer_class = UploadSerializer
    http_method_names = ["get"]
    lookup_field = "id"

    def get(self, request, fileformat, hexsha=None, *args, **kwargs):
        try:
            fileformat = getattr(Format.FileFormat, fileformat.upper())
        except AttributeError:
            return ErrorResponse(
                {"error": f"The file format requested is not recognized: {fileformat}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if fileformat.label.lower() not in Format.FileFormat.download_choices:
            msg = f"The format: {fileformat} is not supported for download"
            logger.exception(f"{msg}, expected: {Format.FileFormat.download_choices}")
            return ErrorResponse(
                {"error": msg},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project: Project = self.get_object()

        try:
            processor = AutoSelector.get_download_processor(
                fileformat=fileformat, project=project, hexsha=hexsha
            )

        except (ValidationError, FileNotFoundError) as e:
            return ErrorResponse({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        with tempfile.NamedTemporaryFile() as temp_file:
            try:
                temp_filepath = pathlib.Path(temp_file.name)

                try:
                    filename: str = processor.get_file_for_download(
                        target_f=temp_filepath
                    )
                except ValidationError as e:
                    raise Http404(
                        f"The file: `{processor.TARGET_SAVE_FILENAME}` does not exists."
                    ) from e

                if filename is not None and temp_filepath.is_file():
                    return DownloadResponseFromFile(
                        filename=filename,
                        filepath=temp_filepath,
                        attachment=True,
                    )

            except ProjectNotFound as e:
                return ErrorResponse(
                    {"error": str(e)}, status=status.HTTP_404_NOT_FOUND
                )

            except RuntimeError as e:
                logger.exception(
                    f"Error - While getting the file to download @ `{hexsha}`"
                )
                return ErrorResponse(
                    {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
                )

            except GitlabError:
                logger.exception("There has been a problem accessing gitlab")
                return ErrorResponse(
                    {"error": "There has been a problem accessing gitlab"},
                    status=status.HTTP_400_BAD_REQUEST,
                )


class BlobDownloadView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [UserHasReadAccess]
    serializer_class = UploadSerializer
    http_method_names = ["get"]
    lookup_field = "id"

    def get(self, request, hexsha: str, *args, **kwargs):
        project: Project = self.get_object()

        for retry_attempt in range(2):
            with contextlib.suppress(GitBlobNotFoundError):
                obj = project.git_repo.find_blob(hexsha)
                return DownloadResponseFromBlob(
                    obj=obj.content, filename=obj.name, attachment=True
                )

            if retry_attempt == 0:
                # Ensure we pull the project to update just in case
                project.checkout_commit_or_default_branch()

        return ErrorResponse(
            {"error": f"Object id=`{hexsha}` not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
