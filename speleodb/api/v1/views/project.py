# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

from django.db.utils import IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import IsObjectDeletion
from speleodb.api.v1.permissions import IsObjectEdition
from speleodb.api.v1.permissions import IsReadOnly
from speleodb.api.v1.permissions import SDB_AdminAccess
from speleodb.api.v1.permissions import SDB_ReadAccess
from speleodb.api.v1.permissions import SDB_WriteAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.git_engine.gitlab_manager import GitlabError
from speleodb.surveys.models import Project
from speleodb.utils.api_mixin import SDBAPIViewMixin
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

    @extend_schema(operation_id="v1_project_retrieve")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        project = self.get_object()
        serializer = self.get_serializer(project, context={"user": user})

        try:
            return SuccessResponse(serializer.data)

        except GitlabError:
            logger.exception("There has been a problem accessing gitlab")
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

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._modify_obj(request=request, partial=False, **kwargs)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._modify_obj(request=request, partial=True, **kwargs)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # Note: We only delete the permissions, rendering the project invisible to the
        # users. After 30 days, the project gets automatically deleted by a cronjob.
        # This is done to protect users from malicious/erronous project deletion.

        user = self.get_user()
        project = self.get_object()
        for perm in project.permissions:
            perm.deactivate(deactivated_by=user)

        project.is_active = False
        project.save()

        user.void_permission_cache()

        return SuccessResponse({"id": str(project.id)})


class ProjectApiView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer

    @extend_schema(operation_id="v1_projects_list")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        project_ids = [perm.project.id for perm in user.permissions]
        projects = (
            Project.objects.with_commits()  # pyright: ignore[reportAttributeAccessIssue]
            .with_commit_count()  # pyright: ignore[reportAttributeAccessIssue]
            .with_active_mutex()  # pyright: ignore[reportAttributeAccessIssue]
            .filter(id__in=project_ids)
        )

        serializer = self.get_serializer(
            projects,
            many=True,
            context={"user": user},
        )

        return SuccessResponse(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()

        data = request.data
        data["created_by"] = user.email

        try:
            serializer = self.get_serializer(data=data, context={"user": user})
            if serializer.is_valid():
                serializer.save()

                user.void_permission_cache()

                return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)

            return ErrorResponse(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        except IntegrityError:
            return ErrorResponse(
                {"error": "This query violates a project requirement"},
                status=status.HTTP_400_BAD_REQUEST,
            )
