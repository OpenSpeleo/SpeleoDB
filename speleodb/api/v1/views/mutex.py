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
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

logger = logging.getLogger(__name__)


class ProjectAcquireApiView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [UserHasWriteAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        project = self.get_object()

        try:
            project.acquire_mutex(user=user)

        except (ValidationError, PermissionError) as e:
            http_status = (
                status.HTTP_403_FORBIDDEN
                if isinstance(e, PermissionError)
                else status.HTTP_400_BAD_REQUEST
            )
            return ErrorResponse({"error": str(e)}, status=http_status)

        # Refresh the `modified_date` field
        project.save()

        serializer = ProjectSerializer(project, context={"user": user})
        return SuccessResponse(serializer.data)


class ProjectReleaseApiView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [UserHasWriteAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        project = self.get_object()
        comment = request.data.get("comment", "")

        try:
            project.release_mutex(user=user, comment=comment)

        except (ValidationError, PermissionError) as e:
            http_status = (
                status.HTTP_403_FORBIDDEN
                if isinstance(e, PermissionError)
                else status.HTTP_400_BAD_REQUEST
            )
            return ErrorResponse({"error": str(e)}, status=http_status)

        # Refresh the `modified_date` field
        project.save()

        serializer = ProjectSerializer(project, context={"user": user})
        return SuccessResponse(serializer.data)
