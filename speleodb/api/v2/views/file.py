# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import io
import logging
import pathlib
import random
import re
import string
import tempfile
from typing import TYPE_CHECKING
from typing import Any
from zipfile import BadZipFile

import sentry_sdk
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db import transaction
from django.http import HttpResponse
from django.urls import reverse
from drf_spectacular.utils import extend_schema
from git.exc import GitCommandError
from rest_framework import status
from rest_framework.exceptions import ParseError
from rest_framework.exceptions import UnsupportedMediaType
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.generics import GenericAPIView

from speleodb.api.v2.permissions import SDB_ReadAccess
from speleodb.api.v2.permissions import SDB_WriteAccess
from speleodb.api.v2.permissions import UserOwnsProjectMutex
from speleodb.api.v2.serializers import ProjectSerializer
from speleodb.api.v2.serializers import UploadSerializer
from speleodb.common.enums import ProjectType
from speleodb.gis.geojson_generation import request_geojson_generation
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.exceptions import GitBlobNotFoundError
from speleodb.git_engine.gitlab_manager import GitlabError
from speleodb.processors import ArianeTMLFileProcessor
from speleodb.processors import AutoSelector
from speleodb.processors import CompassManualFileProcessor
from speleodb.processors._impl.compass_toml import CompassTOML
from speleodb.processors._impl.compass_toml import (
    build_compass_toml_bytes_from_upload_filenames,
)
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import Format
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.exceptions import FileRejectedError
from speleodb.utils.exceptions import ProjectNotFound
from speleodb.utils.helpers import retry_with_backoff
from speleodb.utils.requests import require_mapping_request_data
from speleodb.utils.response import DownloadResponseFromBlob
from speleodb.utils.response import DownloadResponseFromFile
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse
from speleodb.utils.timing_ctx import timed_section

if TYPE_CHECKING:
    from django.http import FileResponse
    from rest_framework.request import Request
    from rest_framework.response import Response


logger = logging.getLogger(__name__)


def upload_input_error(data: dict[str, str], *, status: int) -> ErrorResponse:
    """Report rejected upload input even when validation did not raise."""
    sentry_sdk.capture_message(data["error"], level="error")
    return ErrorResponse(data, status=status)


def handle_exception(
    exception: Exception,
    message: str,
    status_code: int,
    project: Project,
) -> ErrorResponse:
    logger.exception(
        "Upload error for project %s (status=%s): %s",
        project.id,
        status_code,
        exception,
    )
    # HTTP status describes the client response, not whether operators need a report.
    sentry_sdk.capture_exception(exception)

    # Roll back the entire DB transaction so no partial writes (Format
    # rows, ProjectCommit rows, etc.) survive a failed upload.  This is
    # safe for every status code: if we reach this function the upload
    # did not succeed, so nothing should be committed.
    # ATOMIC_REQUESTS is always enabled (set in base.py, no view opts
    # out via @non_atomic_requests), so we are guaranteed to be inside
    # a transaction.atomic() block here.
    transaction.set_rollback(True)

    # Cleanup must never provision a repository after provisioning itself failed.
    # Open the existing working copy directly; the lazy project.git_repo property
    # can create a GitLab project and restart its entire retry budget.
    try:
        if project.git_repo_dir.is_dir():
            git_repo = GitRepo(project.git_repo_dir)
            with git_repo:
                git_repo.reset_and_remove_untracked()
    except Exception as cleanup_error:
        logger.warning(
            "Failed to reset git working tree for project %s",
            project.id,
            exc_info=True,
        )
        sentry_sdk.capture_exception(cleanup_error)

    error_msg = message.format(exception)
    return ErrorResponse({"error": error_msg}, status=status_code)


def request_uploaded_geojson(
    project: Project, hexsha: str, uploaded_files: list[pathlib.Path]
) -> str:
    """Record optional work after a successful push; never contact the broker.

    The dispatcher sees this record only after ATOMIC_REQUESTS commits. A failed
    bookkeeping write rolls back its own savepoint, preserving the source upload.
    Operators can retry the pushed commit from administration if recording fails.
    """
    if project.exclude_geojson:
        return "skipped"
    eligible = any(
        (
            project.type == ProjectType.ARIANE
            and file.name == ArianeTMLFileProcessor.TARGET_SAVE_FILENAME
        )
        or (
            project.type == ProjectType.COMPASS
            and (
                file.name == CompassTOML.__FILENAME__
                or file.suffix.lower() in {".mak", ".dat", ".plt"}
            )
        )
        for file in uploaded_files
    )
    if not eligible:
        return "not_requested"

    try:
        with transaction.atomic():
            commit = ProjectCommit.objects.get(pk=hexsha, project=project)
            generation = request_geojson_generation(project, commit)
        return str(generation.state)
    except Exception as error:
        logger.exception(
            "Unable to schedule GeoJSON for saved project %s at %s", project.pk, hexsha
        )
        # Telemetry is optional too; a reporting transport must not reject source.
        with contextlib.suppress(Exception):
            sentry_sdk.capture_exception(error)
        return "unavailable"


class FileUploadView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [SDB_WriteAccess, UserOwnsProjectMutex]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def handle_exception(self, exc: Exception) -> Response:
        # DRF handles parser errors before Django can emit got_request_exception.
        # Authentication/permission failures are outside upload processing.
        if isinstance(exc, (ParseError, UnsupportedMediaType, DRFValidationError)):
            sentry_sdk.capture_exception(exc)
        return super().handle_exception(exc)

    @extend_schema(operation_id="v2_projects_upload")
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
                    return upload_input_error(
                        {"error": msg},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # ~~~~~~~~~~~~~~~~~~~~~~~ END of URL Validation ~~~~~~~~~~~~~~~~~~~~~ #

            # ~~~~~~~~~~~~~~~~~~ START of Form Data Validation ~~~~~~~~~~~~~~~~~~ #
            with timed_section("Form Data Validation"):
                try:
                    files = request.FILES.getlist("artifact")
                except KeyError:
                    return upload_input_error(
                        {"error": "Uploaded file(s) `artifact` is/are missing."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Verify the commit message is not empty
                request_data = require_mapping_request_data(request.data)
                if not (commit_message := request_data.get("message", "")):
                    data = {
                        "error": (
                            f"Empty or no `message` received: `{commit_message}`."
                        )
                    }
                    return upload_input_error(data, status=status.HTTP_400_BAD_REQUEST)

                # Remove front and back `\n\r and spaces and in the middle`
                commit_message = re.sub(r"(?:\s*\n\s*)+", ". ", commit_message.strip())

                # Verify there's at least one file
                if not files:
                    return upload_input_error(
                        {"error": "No files uploaded"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Verify there's a maximum of `DJANGO_UPLOAD_TOTAL_FILES_LIMIT` files
                # uploaded in one API call.
                if len(files) > settings.DJANGO_UPLOAD_TOTAL_FILES_LIMIT:
                    return upload_input_error(
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
                        return upload_input_error(
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
                        return upload_input_error(
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
                        return upload_input_error(
                            {"error": f"Unknown artifact received: `{file.name}`"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                if (
                    total_filesize
                    > settings.DJANGO_UPLOAD_TOTAL_FILES_LIMIT * 1024 * 1204
                ):
                    return upload_input_error(
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
            project = self.get_object()
            auto_compass_toml_generated = False

            try:
                if fileformat_f == FileFormat.AUTO:
                    with timed_section("AUTO - Compass TOML generation"):
                        compass_toml_bytes = (
                            build_compass_toml_bytes_from_upload_filenames(
                                project_id=project.id,
                                filenames=[
                                    str(file.name or "")
                                    for file in files
                                    if file.name is not None
                                ],
                            )
                        )

                        if compass_toml_bytes is not None:
                            files = [
                                file
                                for file in files
                                if (file.name or "").lower() != CompassTOML.__FILENAME__
                            ]
                            toml_file_obj = io.BytesIO(compass_toml_bytes)
                            files.append(
                                InMemoryUploadedFile(
                                    file=toml_file_obj,
                                    field_name="artifact",
                                    name=CompassTOML.__FILENAME__,
                                    content_type="text/plain",
                                    size=len(compass_toml_bytes),
                                    charset="utf-8",
                                )
                            )
                            auto_compass_toml_generated = True

                with timed_section("Git Project - Checkout and Pull"):
                    # Make sure the project is update to ToT (Top of Tree)
                    project.checkout_commit_or_default_pull_branch()

                with timed_section("Project Edition - File Adding - Git Commit & Push"):
                    uploaded_files: list[pathlib.Path] = []

                    for file in files:
                        if fileformat_f == FileFormat.COMPASS_ZIP:
                            # Verify .zip extension (case-insensitive)
                            if not file.name.lower().endswith(".zip"):
                                return upload_input_error(
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
                                processor = retry_with_backoff(
                                    AutoSelector.get_upload_processor,
                                    retries=settings.DJANGO_GIT_RETRY_ATTEMPTS,
                                    exc_types=(GitCommandError,),
                                    fileformat=fileformat_f,
                                    file=file,
                                    project=project,
                                )

                            with timed_section("File Management"):
                                if fileformat_f == FileFormat.AUTO:
                                    if auto_compass_toml_generated and isinstance(
                                        processor, CompassManualFileProcessor
                                    ):
                                        target_fileformat = FileFormat.COMPASS_ZIP
                                    else:
                                        target_fileformat = processor.ASSOC_FILEFORMAT
                                else:
                                    target_fileformat = fileformat_f

                                # Associates the project with the format, ignore if
                                # already done. We have to start with this in order to
                                # have: `commit_date` > creation_date.
                                Format.objects.get_or_create(
                                    project=project, _format=target_fileformat
                                )

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

                                except (
                                    BadZipFile,
                                    ValueError,
                                    TypeError,
                                    ValidationError,
                                ) as e:
                                    if settings.DEBUG:
                                        raise

                                    return handle_exception(
                                        e,
                                        "An error occurred processing the file: {}",
                                        status.HTTP_400_BAD_REQUEST,
                                        project,
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

                    # Git push has completed. Record durable work in this request's
                    # SQL transaction; only the background dispatcher enqueues it.
                    geojson_status = request_uploaded_geojson(
                        project, hexsha, uploaded_files
                    )

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
                                "geojson_status": geojson_status,
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
                    project,
                )

            except GitlabError as e:
                if settings.DEBUG:
                    raise

                return handle_exception(
                    e,
                    "There has been a problem accessing GitLab: `{}`",
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    project,
                )

            except FileRejectedError as e:
                if settings.DEBUG:
                    raise

                return handle_exception(
                    e,
                    "One of the uploaded files has been rejected: `{}`",
                    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    project,
                )

            except Exception as e:
                if settings.DEBUG:
                    raise

                return handle_exception(
                    e,
                    "There has been a problem committing the files: {}",
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    project,
                )


class FileDownloadView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [SDB_ReadAccess]
    serializer_class = UploadSerializer
    http_method_names = ["get"]
    lookup_field = "id"

    @extend_schema(operation_id="v2_projects_download_retrieve_by_format")
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

        except RuntimeError as e:
            logger.exception("Download error for project %s", project.id)
            sentry_sdk.capture_exception(e)
            return ErrorResponse(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        except GitlabError as e:
            logger.exception("GitLab error during download for project %s", project.id)
            sentry_sdk.capture_exception(e)
            return ErrorResponse(
                {"error": "There has been a problem accessing gitlab"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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
                logger.exception("Download error for project %s", project.id)
                sentry_sdk.capture_exception(e)
                return ErrorResponse(
                    {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            except GitlabError as e:
                logger.exception(
                    "GitLab error during download for project %s", project.id
                )
                sentry_sdk.capture_exception(e)
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

    @extend_schema(operation_id="v2_projects_download_blob_retrieve")
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

    @extend_schema(operation_id="v2_projects_download_retrieve_by_format_at_hash")
    def get(
        self,
        request: Request,
        fileformat: str,
        hexsha: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> Response | FileResponse:
        return super().get(request, fileformat, hexsha, *args, **kwargs)
