#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from typing import Any

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from speleodb.api.v1.permissions import UserHasWriteAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.surveys.models import Project
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

logger = logging.getLogger(__name__)


class ProjectAcquireApiView(GenericAPIView[Project]):
    queryset = Project.objects.all()
    permission_classes = [UserHasWriteAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def post(
        self, request: Request, *args: list[Any], **kwargs: dict[str, Any]
    ) -> Response:
        project: Project = self.get_object()

        try:
            project.acquire_mutex(user=request.user)  # type: ignore[arg-type]

        except (ValidationError, PermissionError) as e:
            http_status = (
                status.HTTP_403_FORBIDDEN
                if isinstance(e, PermissionError)
                else status.HTTP_400_BAD_REQUEST
            )
            return ErrorResponse({"error": str(e)}, status=http_status)

        # Refresh the `modified_date` field
        project.save()

        serializer = ProjectSerializer(project, context={"user": request.user})
        return SuccessResponse(serializer.data)


class ProjectReleaseApiView(GenericAPIView[Project]):
    queryset = Project.objects.all()
    permission_classes = [UserHasWriteAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def post(
        self, request: Request, *args: list[Any], **kwargs: dict[str, Any]
    ) -> Response:
        project: Project = self.get_object()
        comment = request.data.get("comment", "")

        try:
            project.release_mutex(user=request.user, comment=comment)  # type: ignore[arg-type]

        except (ValidationError, PermissionError) as e:
            http_status = (
                status.HTTP_403_FORBIDDEN
                if isinstance(e, PermissionError)
                else status.HTTP_400_BAD_REQUEST
            )
            return ErrorResponse({"error": str(e)}, status=http_status)

        # Refresh the `modified_date` field
        project.save()

        serializer = ProjectSerializer(project, context={"user": request.user})
        return SuccessResponse(serializer.data)
