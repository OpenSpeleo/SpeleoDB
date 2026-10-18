# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

import sentry_sdk
from django.db.utils import IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.schema_errors import API_ERROR
from speleodb.api.v2.permissions import IsObjectDeletion
from speleodb.api.v2.permissions import IsObjectEdition
from speleodb.api.v2.permissions import IsReadOnly
from speleodb.api.v2.permissions import SDB_AdminAccess
from speleodb.api.v2.permissions import SDB_ReadAccess
from speleodb.api.v2.permissions import SDB_WriteAccess
from speleodb.api.v2.serializers import ProjectSerializer
from speleodb.api.v2.serializers.api_contract import IdentifierSerializer
from speleodb.git_engine.gitlab_manager import GitlabError
from speleodb.surveys.models import Project
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.requests import require_mapping_request_data
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response

logger = logging.getLogger(__name__)


class ProjectSpecificApiView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [
        (IsObjectDeletion & SDB_AdminAccess)
        | (IsObjectEdition & SDB_WriteAccess)
        | (IsReadOnly & SDB_ReadAccess)
    ]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    @extend_schema(operation_id="v2_project_retrieve")
    @extend_schema(responses={200: ProjectSerializer(), 403: API_ERROR, 500: API_ERROR})
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        project = self.get_object()
        serializer = self.get_serializer(project, context={"user": user})

        try:
            return SuccessResponse(serializer.data)

        except GitlabError as e:
            logger.exception("There has been a problem accessing gitlab")
            sentry_sdk.capture_exception(e)
            return ErrorResponse(
                {"error": "There has been a problem accessing gitlab"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _modify_obj(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        user = self.get_user()
        project = self.get_object()
        serializer = self.get_serializer(
            project,
            data=request.data,
            context={"user": user},
            partial=partial,
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    @extend_schema(operation_id="v2_projects_update")
    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._modify_obj(request=request, partial=False, **kwargs)

    @extend_schema(operation_id="v2_projects_partial_update")
    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._modify_obj(request=request, partial=True, **kwargs)

    @extend_schema(responses={200: IdentifierSerializer, 403: API_ERROR})
    @extend_schema(operation_id="v2_projects_destroy")
    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # Note: We only delete the permissions, rendering the project invisible to the
        # users. After 30 days, the project gets automatically deleted by a cronjob.
        # This is done to protect users from malicious/erronous project deletion.

        user = self.get_user()
        project = self.get_object()
        for perm in project.permissions:
            perm.deactivate(deactivated_by=user)

        project.is_active = False
        project.save(update_fields=["is_active"])

        return SuccessResponse({"id": str(project.id)})


class ProjectApiView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer

    @extend_schema(
        operation_id="v2_projects_list",
        responses={200: ProjectSerializer(many=True), 403: API_ERROR},
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        project_ids = [perm.project.id for perm in user.permissions]
        projects = (
            Project.objects.with_commits()  # pyright: ignore[reportAttributeAccessIssue]
            .with_commit_count()  # pyright: ignore[reportAttributeAccessIssue]
            .with_active_mutex()  # pyright: ignore[reportAttributeAccessIssue]
            .prefetch_related("_formats")
            .filter(id__in=project_ids)
        )

        serializer = self.get_serializer(
            projects,
            many=True,
            context={"user": user},
        )

        return SuccessResponse(serializer.data)

    @extend_schema(responses={201: ProjectSerializer, 400: API_ERROR, 403: API_ERROR})
    @extend_schema(operation_id="v2_projects_create")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()

        data = require_mapping_request_data(request.data).copy()
        data["created_by"] = user.email

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
