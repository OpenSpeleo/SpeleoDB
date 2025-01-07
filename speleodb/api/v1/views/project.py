#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from typing import TYPE_CHECKING

from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import UserHasAdminAccess
from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.permissions import UserHasWriteAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.git_engine.gitlab_manager import GitlabError
from speleodb.surveys.models import Project
from speleodb.utils.api_decorators import method_permission_classes
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from speleodb.users.models import User

logger = logging.getLogger(__name__)


class ProjectSpecificApiView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [UserHasReadAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def get(self, request, *args, **kwargs):
        project: Project = self.get_object()
        serializer = self.get_serializer(project, context={"user": request.user})

        try:
            return SuccessResponse(
                {"project": serializer.data, "history": project.commit_history}
            )
        except GitlabError:
            logger.exception("There has been a problem accessing gitlab")
            return ErrorResponse(
                {"error": "There has been a problem accessing gitlab"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @method_permission_classes((UserHasWriteAccess,))
    def put(self, request, *args, **kwargs):
        project: Project = self.get_object()
        serializer = self.get_serializer(
            project, data=request.data, context={"user": request.user}
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_200_OK)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    @method_permission_classes((UserHasWriteAccess,))
    def patch(self, request, *args, **kwargs):
        project: Project = self.get_object()
        serializer = self.get_serializer(
            project, data=request.data, context={"user": request.user}, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_200_OK)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    @method_permission_classes((UserHasAdminAccess,))
    def delete(self, request, *args, **kwargs):
        # Note: We only delete the permissions, rendering the project invisible to the
        # users. After 30 days, the project gets automatically deleted by a cronjob.
        # This is done to protect users from malicious/erronous project deletion.

        project: Project = self.get_object()
        for perm in project.permissions:
            perm.deactivate(deactivated_by=request.user)

        return SuccessResponse({"id": str(project.id)})


class ProjectApiView(GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer
    queryset = Project.objects.all()

    def get(self, request, *args, **kwargs):
        user: User = request.user

        serializer = self.get_serializer(
            user.projects, many=True, context={"user": user}
        )

        return SuccessResponse(serializer.data)

    def post(self, request, *args, **kwargs):
        user: User = request.user

        data = request.data
        data["created_by"] = user

        serializer = self.get_serializer(data=data, context={"user": user})
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )
