#!/usr/bin/env python
# -*- coding: utf-8 -*-

import contextlib
import logging
import pathlib
import tempfile

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.permissions import UserHasWriteAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.serializers import UploadSerializer
from speleodb.processors.auto_selector import AutoSelector
from speleodb.surveys.models import Format
from speleodb.surveys.models import Project
from speleodb.utils.exceptions import ProjectNotFound
from speleodb.utils.gitlab_manager import GitlabError
from speleodb.utils.gitlab_manager import GitlabManager
from speleodb.utils.response import DownloadResponseFromFile
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

logger = logging.getLogger(__name__)


class FileUploadView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasWriteAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def put(self, request, fileformat, *args, **kwargs):  # noqa: PLR0911
        try:
            fileformat = getattr(Format.FileFormat, fileformat.upper())
        except AttributeError:
            return ErrorResponse(
                {"error": f"The file format requested is not recognized: {fileformat}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if fileformat.label.lower() not in Format.FileFormat.upload_choices:
            msg = f"The format: {fileformat} is not supported for upload"
            logger.exception(f"{msg}, expected: {Format.FileFormat.upload_choices}")  # noqa: G004
            return ErrorResponse(
                {"error": msg},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = self.get_object()

        commit_message = request.data.get("message", None)
        if commit_message is None or commit_message == "":
            data = {"error": (f"Empty or no `message` received: `{commit_message}`.")}
            return ErrorResponse(data, status=status.HTTP_400_BAD_REQUEST)

        try:
            file_uploaded = request.data["artifact"]
        except KeyError:
            return ErrorResponse(
                {"error": "Uploaded file `artifact is missing.`"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            processor = AutoSelector.get_upload_processor(
                fileformat=fileformat, file=file_uploaded, project=project
            )

            if fileformat == Format.FileFormat.AUTO:
                fileformat = processor.ASSOC_FILEFORMAT

        except (ValidationError, FileNotFoundError) as e:
            return ErrorResponse({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Associating the project with the format - ignore if already done.
        # We have to start with this in order to have `commit_date` > creation_date.
        with contextlib.suppress(IntegrityError):
            f_obj, created = Format.objects.get_or_create(
                project=project, _format=fileformat
            )

        try:
            file, commit_sha1 = processor.commit_file(
                file=file_uploaded,
                user=request.user,
                commit_msg=commit_message,
            )

        except (ValidationError, FileNotFoundError) as e:
            if created:
                f_obj.delete()
            return ErrorResponse({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except GitlabError:
            if created:
                f_obj.delete()
            logger.exception("There has been a problem accessing gitlab")
            return ErrorResponse(
                {"error": "There has been a problem accessing gitlab"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception as e:
            if created:
                f_obj.delete()
            logger.exception("There has been a problem committing the file")
            return ErrorResponse(
                {"error": f"There has been a problem committing the file: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Void Gitlab API Cache for this project.
        GitlabManager.void_project_gitlab_cache(project_id=project.id)

        # Refresh the `modified_date` field
        project.save()

        return SuccessResponse(
            {
                "content_type": file.content_type,
                "message": commit_message,
                "commit_sha1": commit_sha1,
                "project": ProjectSerializer(
                    project, context={"user": request.user}
                ).data,
            }
        )


class FileDownloadView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasReadAccess]
    serializer_class = UploadSerializer
    http_method_names = ["get"]
    lookup_field = "id"

    def get(self, request, fileformat, commit_sha1=None, *args, **kwargs):
        try:
            fileformat = getattr(Format.FileFormat, fileformat.upper())
        except AttributeError:
            return ErrorResponse(
                {"error": f"The file format requested is not recognized: {fileformat}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if fileformat.label.lower() not in Format.FileFormat.download_choices:
            msg = f"The format: {fileformat} is not supported for download"
            logger.exception(f"{msg}, expected: {Format.FileFormat.download_choices}")  # noqa: G004
            return ErrorResponse(
                {"error": msg},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = self.get_object()

        try:
            processor = AutoSelector.get_download_processor(
                fileformat=fileformat, project=project, commit_sha1=commit_sha1
            )

        except (ValidationError, FileNotFoundError) as e:
            return ErrorResponse({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_filepath = pathlib.Path(temp_file.name)
            filename = processor.get_file_for_download(target_f=temp_filepath)

            return DownloadResponseFromFile(
                filename=filename,
                filepath=temp_filepath,
                attachment=False,
            )

        except ProjectNotFound as e:
            return ErrorResponse({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

        except GitlabError:
            logger.exception("There has been a problem accessing gitlab")
            return ErrorResponse(
                {"error": "There has been a problem accessing gitlab"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        finally:
            pathlib.Path(temp_file.name).unlink()
