# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

from django.db.models import F
from django.db.models import TextField
from django.db.models.functions import Cast
from django.db.utils import IntegrityError
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import UserHasAdminAccess
from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.permissions import UserHasWebViewerAccess
from speleodb.api.v1.permissions import UserHasWriteAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.git_engine.gitlab_manager import GitlabError
from speleodb.surveys.models import Project
from speleodb.utils.api_decorators import method_permission_classes
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response

logger = logging.getLogger(__name__)


class ProjectSpecificApiView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [UserHasReadAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        project = self.get_object()
        serializer = self.get_serializer(project, context={"user": user})

        try:
            return SuccessResponse(
                {"project": serializer.data, "history": project.commit_history}
            )
        except GitlabError:
            logger.exception("There has been a problem accessing gitlab")
            return ErrorResponse(
                {"error": "There has been a problem accessing gitlab"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @method_permission_classes((UserHasWriteAccess,))
    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        project = self.get_object()
        serializer = self.get_serializer(
            project, data=request.data, context={"user": user}
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_200_OK)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    @method_permission_classes((UserHasWriteAccess,))
    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        project = self.get_object()
        serializer = self.get_serializer(
            project, data=request.data, context={"user": user}, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_200_OK)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    @method_permission_classes((UserHasAdminAccess,))
    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # Note: We only delete the permissions, rendering the project invisible to the
        # users. After 30 days, the project gets automatically deleted by a cronjob.
        # This is done to protect users from malicious/erronous project deletion.

        user = self.get_user()
        project = self.get_object()
        for perm in project.permissions:
            perm.deactivate(deactivated_by=user)

        return SuccessResponse({"id": str(project.id)})


class ProjectApiView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()

        serializer = self.get_serializer(
            user.projects, many=True, context={"user": user}
        )

        return SuccessResponse(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()

        data = request.data
        data["created_by"] = user

        try:
            serializer = self.get_serializer(data=data, context={"user": user})
            if serializer.is_valid():
                serializer.save()
                return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)

            return ErrorResponse(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        except IntegrityError:
            return ErrorResponse(
                {"error": "This query violates a project requirement"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ProjectGeoJsonApiView(GenericAPIView[Project], SDBAPIViewMixin):
    """API view that returns raw GeoJSON data for a project."""

    queryset = Project.objects.all()
    permission_classes = [UserHasWebViewerAccess]
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Return the raw GeoJSON data as JSON response."""
        # First check permissions by getting the object normally
        project = self.get_object()

        # Now fetch the raw geojson field as string using Cast to avoid dict conversion
        raw_json_string = (
            Project.objects.annotate(
                raw_json=Cast(F("geojson"), output_field=TextField())
            )
            .values_list("raw_json", flat=True)
            .get(id=project.id)
        )

        # Return the raw JSON string directly as data - never parse it in Python
        return SuccessResponse(raw_json_string or "{}")
