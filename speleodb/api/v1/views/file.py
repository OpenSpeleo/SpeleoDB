# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
import pathlib
import random
import re
import string
import tempfile
from collections import defaultdict
from typing import TYPE_CHECKING
from typing import Any

import orjson
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db import transaction
from django.http import HttpResponse
from django.urls import reverse
from drf_spectacular.utils import extend_schema
from git.exc import GitCommandError
from openspeleo_lib.errors import EmptySurveyError
from openspeleo_lib.geojson import NoKnownAnchorError
from openspeleo_lib.geojson import survey_to_geojson
from openspeleo_lib.interfaces import ArianeInterface
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import SDB_ReadAccess
from speleodb.api.v1.permissions import SDB_WriteAccess
from speleodb.api.v1.permissions import UserOwnsProjectMutex
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.serializers import UploadSerializer
from speleodb.gis.models import ProjectGeoJSON
from speleodb.git_engine.exceptions import GitBlobNotFoundError
from speleodb.git_engine.gitlab_manager import GitlabError
from speleodb.processors.auto_selector import AutoSelector
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import Format
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.exceptions import FileRejectedError
from speleodb.utils.exceptions import ProjectNotFound
from speleodb.utils.response import DownloadResponseFromBlob
from speleodb.utils.response import DownloadResponseFromFile
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse
from speleodb.utils.timing_ctx import timed_section

if TYPE_CHECKING:
    from django.http import FileResponse
    from openspeleo_lib.models import Survey
    from rest_framework.request import Request
    from rest_framework.response import Response


logger = logging.getLogger(__name__)


def handle_exception(
    exception: Exception,
    message: str,
    status_code: int,
    format_assoc: dict[Format, bool],
    project: Project,
) -> ErrorResponse:
    additional_errors = []
    # Cleanup created formats
    for f_obj, created in format_assoc.items():
        if created:
            try:
                f_obj.delete()
            except Exception:  # noqa: BLE001
                additional_errors.append(
                    "Error during removal of created new format association"
                )

    # Reset project state
    try:
        project.git_repo.reset_and_remove_untracked()
    except Exception:  # noqa: BLE001
        additional_errors.append(
            "Error during resetting of the project to HEAD and removal of untracked "
            "files."
        )

    error_msg = message.format(exception)

    if additional_errors:
        error_msg += " - Additional Errors During Exception Handling: "
        error_msg += ", ".join(additional_errors)

    return ErrorResponse({"error": error_msg}, status=status_code)


class FileUploadView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [SDB_WriteAccess, UserOwnsProjectMutex]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    @extend_schema(operation_id="v1_projects_upload")
    def put(
        self,
        request: Request,
        fileformat: str,
        *args: Any,
        **kwargs: Any,
    ) -> Response | HttpResponse:
        user = self.get_user()
        with timed_section("Project Upload"):
            # ~~~~~~~~~~~~~~~~~~~~~~ START of URL Validation ~~~~~~~~~~~~~~~~~~~~ #
            with timed_section("URL Validation"):
                fileformat_f = FileFormat.from_str(fileformat.upper())

                if fileformat_f.label.lower() not in FileFormat.upload_choices:
                    msg = f"The format: {fileformat_f} is not supported for upload"
                    logger.exception(f"{msg}, expected: {FileFormat.upload_choices}")
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

                # Verify the commit message is not empty
                if not (commit_message := request.data.get("message", "")):
                    data = {
                        "error": (
                            f"Empty or no `message` received: `{commit_message}`."
                        )
                    }
                    return ErrorResponse(data, status=status.HTTP_400_BAD_REQUEST)

                # Remove front and back `\n\r and spaces and in the middle`
                commit_message = re.sub(r"(?:\s*\n\s*)+", ". ", commit_message.strip())

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

                # ================== COMPASS ZIP =================== #
                # Only one file allowed for Compass ZIP uploads
                if fileformat_f == FileFormat.COMPASS_ZIP:
                    if len(files) != 1:
                        return ErrorResponse(
                            {
                                "error": (
                                    "Only one file upload is allowed for "
                                    "Compass ZIP format."
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
                                    f"[{file.size / 1024.0 / 1204.0} Mb], exceeds the limit: "  # noqa: E501
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
                                f"[{total_filesize / 1024.0 / 1204.0} Mb], exceeds the "
                                f"limit: {settings.DJANGO_UPLOAD_TOTAL_FILES_LIMIT} Mb"
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # ~~~~~~~~~~~~~~~~~~~~ END of Form Data Validation ~~~~~~~~~~~~~~~~~~~~ #

            # ~~~~~~~~~~~~~~~~~ START of writing files to project ~~~~~~~~~~~~~~~~~ #
            format_assoc: dict[Format, bool] = defaultdict(lambda: False)
            project = self.get_object()

            try:
                with timed_section("Git Project - Checkout and Pull"):
                    # Make sure the project is update to ToT (Top of Tree)
                    project.checkout_commit_or_default_pull_branch()

                with timed_section("Project Edition - File Adding - Git Commit & Push"):
                    uploaded_files: list[pathlib.Path] = []

                    for file in files:
                        if fileformat_f == FileFormat.COMPASS_ZIP:
                            # Verify .zip extension (case-insensitive)
                            if not file.name.lower().endswith(".zip"):
                                return ErrorResponse(
                                    {
                                        "error": (
                                            f"Compass ZIP upload must have a "
                                            f"'.zip' extension. Got `{file.name}`."
                                        )
                                    },
                                    status=status.HTTP_400_BAD_REQUEST,
                                )

                            # Change extension from .zip -> .czip
                            base_name = file.name.rsplit(".", 1)[0]
                            file.name = f"{base_name}.czip"

                        with timed_section(f"File Adding: `{file.name}`"):
                            # maximum retry attempts in case of Git exception
                            with timed_section("Get Upload Processor"):
                                git_error = None
                                for _ in range(5):
                                    try:
                                        processor = AutoSelector.get_upload_processor(
                                            fileformat=fileformat_f,
                                            file=file,
                                            project=project,
                                        )
                                        break
                                    except GitCommandError as e:
                                        git_error = str(e)
                                else:
                                    return ErrorResponse(
                                        {"error": f"Git Error: {git_error}"},
                                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    )

                            with timed_section("File Management"):
                                if fileformat_f == FileFormat.AUTO:
                                    target_fileformat = processor.ASSOC_FILEFORMAT
                                else:
                                    target_fileformat = fileformat_f

                                # Associates the project with the format, ignore if
                                # already done. We have to start with this in order to
                                # have: `commit_date` > creation_date.
                                f_obj, created = Format.objects.get_or_create(
                                    project=project, _format=target_fileformat
                                )
                                format_assoc[f_obj] = format_assoc[f_obj] or created

                                try:
                                    with timed_section("File copy to project"):
                                        uploaded_files.extend(
                                            processor.add_to_project(file=file)
                                        )

                                except FileExistsError:
                                    logger.info(
                                        f"File collision detected for: `{file.name}` "
                                        "- Skipping ..."
                                    )
                                    continue

                                except (ValueError, TypeError, ValidationError) as e:
                                    logger.exception("Error converting to GeoJSON")
                                    return ErrorResponse(
                                        {"error": str(e)},
                                        status=status.HTTP_400_BAD_REQUEST,
                                    )

                    with timed_section("GIT Commit and Push"):
                        # Finally commit the project - None if project not dirty
                        hexsha: str | None = project.commit_and_push_project(
                            message=commit_message,
                            author=user,
                        )

                    if hexsha is None:
                        with timed_section("HTTP Error Response Construction"):
                            return HttpResponse(status=304)

                    with timed_section("Conversion to GeoJSON"):
                        for file in uploaded_files:
                            if (
                                file.name == "project.tml"
                                and not project.exclude_geojson
                            ):
                                try:
                                    survey: Survey = ArianeInterface.from_file(file)
                                    geojson_data = survey_to_geojson(survey)

                                    geojson_f = SimpleUploadedFile(
                                        "test.geojson",  # filename
                                        orjson.dumps(geojson_data),
                                        content_type="application/geo+json",
                                    )
                                except NoKnownAnchorError:
                                    logger.info(
                                        "No known GPS anchor was found for project "
                                        f"`{project.id}`. Skipping GeoJSON..."
                                    )
                                    continue

                                except EmptySurveyError:
                                    logger.info(
                                        "Empty survey. No shots for project "
                                        f"`{project.id}`. Skipping GeoJSON..."
                                    )
                                    continue

                                except Exception:
                                    logger.exception("Error converting to GeoJSON")
                                    continue

                                try:
                                    with transaction.atomic():
                                        # This object must exist.
                                        commit_obj = ProjectCommit.objects.get(
                                            id=hexsha
                                        )

                                        ProjectGeoJSON.objects.create(
                                            project=project,
                                            commit=commit_obj,
                                            file=geojson_f,
                                        )

                                except ClientError:
                                    # # This ensures the atomic block is rolled back
                                    # transaction.set_rollback(True)
                                    logger.exception("Error uploading GeoJSON to S3.")
                                    continue

                                # There can be only one file called `project.tml`
                                # No point to continue the loop.
                                break

                    with timed_section("HTTP Success Response Construction"):
                        # Refresh the `modified_date` field
                        project.save()

                        uploaded_path = [
                            f if isinstance(f, pathlib.Path) else f.path
                            for f in uploaded_files
                        ]

                        return SuccessResponse(
                            {
                                "files": [
                                    str(f.relative_to(project.git_repo_dir))
                                    for f in uploaded_path
                                ],
                                "message": commit_message,
                                "hexsha": hexsha,
                                "browser_url": (
                                    reverse(
                                        "private:project_revision_explorer",
                                        kwargs={
                                            "project_id": project.id,
                                            "hexsha": hexsha,
                                        },
                                    )
                                    if hexsha is not None
                                    else None
                                ),
                                "project": ProjectSerializer(
                                    project,
                                    context={"user": user},
                                ).data,
                            }
                        )

            except (ValidationError, FileNotFoundError) as e:
                if settings.DEBUG:
                    raise

                return handle_exception(
                    e,
                    "An error occurred: {}",
                    status.HTTP_400_BAD_REQUEST,
                    format_assoc,
                    project,
                )

            except GitlabError as e:
                if settings.DEBUG:
                    raise

                return handle_exception(
                    e,
                    "There has been a problem accessing GitLab: `{}`",
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    format_assoc,
                    project,
                )

            except FileRejectedError as e:
                if settings.DEBUG:
                    raise

                return handle_exception(
                    e,
                    "One of the uploaded files has been rejected: `{}`",
                    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    format_assoc,
                    project,
                )

            except Exception as e:
                if settings.DEBUG:
                    raise

                return handle_exception(
                    e,
                    "There has been a problem committing the files: {}",
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    format_assoc,
                    project,
                )


class FileDownloadView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [SDB_ReadAccess]
    serializer_class = UploadSerializer
    http_method_names = ["get"]
    lookup_field = "id"

    @extend_schema(operation_id="v1_projects_download_retrieve_by_format")
    def get(
        self,
        request: Request,
        fileformat: str,
        hexsha: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> Response | FileResponse:
        try:
            fileformat_f: FileFormat = getattr(FileFormat, fileformat.upper())
        except AttributeError:
            return ErrorResponse(
                {"error": f"The file format requested is not recognized: {fileformat}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if fileformat_f.label.lower() not in FileFormat.download_choices:
            msg = f"The format: {fileformat_f} is not supported for download"
            logger.exception(f"{msg}, expected: {FileFormat.download_choices}")
            return ErrorResponse(
                {"error": msg},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = self.get_object()

        try:
            processor = AutoSelector.get_download_processor(
                fileformat=fileformat_f, project=project, hexsha=hexsha
            )

        except FileNotFoundError as e:
            return ErrorResponse(
                {"error": str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        except ValidationError as e:
            return ErrorResponse({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        with tempfile.TemporaryDirectory() as tempdir:
            try:
                temp_filepath = (
                    pathlib.Path(tempdir)
                    / f"{''.join(random.choice(string.ascii_letters) for _ in range(10))}.obj"  # noqa: E501
                )

                try:
                    filename = processor.get_filename_for_download(
                        target_f=temp_filepath, hexsha=hexsha
                    )
                except FileNotFoundError as e:
                    return ErrorResponse(
                        {"error": str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
                    )
                except ValidationError:
                    return ErrorResponse(
                        {
                            "error": (
                                f"The file: `{processor.TARGET_SAVE_FILENAME}` does "
                                "not exists."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if filename is not None and temp_filepath.is_file():
                    return DownloadResponseFromFile(
                        filepath=temp_filepath,
                        filename=str(filename),
                        attachment=True,
                    )

                return ErrorResponse(
                    {"error": "File not found ..."}, status=status.HTTP_404_NOT_FOUND
                )

            except ProjectNotFound as e:
                return ErrorResponse(
                    {"error": str(e)}, status=status.HTTP_404_NOT_FOUND
                )

            except RuntimeError as e:
                return ErrorResponse(
                    {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            except GitlabError:
                return ErrorResponse(
                    {"error": "There has been a problem accessing gitlab"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )


class BlobDownloadView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [SDB_ReadAccess]
    serializer_class = UploadSerializer
    http_method_names = ["get"]
    lookup_field = "id"

    @extend_schema(operation_id="v1_projects_download_blob_retrieve")
    def get(
        self,
        request: Request,
        hexsha: str,
        *args: Any,
        **kwargs: Any,
    ) -> Response | FileResponse:
        project = self.get_object()

        # Using a retry-loop to prevent "pulling the repo" first.
        # If - by any chance - the blob is already known by GIT, we can reply fast
        # Otherwise, we detect the blob to not be found and pull the repo and try again.
        for retry_attempt in range(2):
            with contextlib.suppress(GitBlobNotFoundError):
                obj = project.git_repo.find_blob(hexsha)
                return DownloadResponseFromBlob(
                    obj=obj.content, filename=obj.name, attachment=True
                )

            if retry_attempt == 0:
                # Ensure we pull the project to update just in case
                project.checkout_commit_or_default_pull_branch()

        return ErrorResponse(
            {"error": f"Object id=`{hexsha}` not found."},
            status=status.HTTP_404_NOT_FOUND,
        )


class FileDownloadAtHashView(FileDownloadView):
    """Dedicated view for hexsha route to provide unique operation_id."""

    @extend_schema(operation_id="v1_projects_download_retrieve_by_format_at_hash")
    def get(
        self,
        request: Request,
        fileformat: str,
        hexsha: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> Response | FileResponse:
        return super().get(request, fileformat, hexsha, *args, **kwargs)
