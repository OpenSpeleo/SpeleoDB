#!/usr/bin/env python
# -*- coding: utf-8 -*-

import contextlib
import logging

from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.serializers import CommitListSerializer
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.surveys.models import Project
from speleodb.utils.api_decorators import method_permission_classes
from speleodb.utils.gitlab_manager import GitlabError
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

logger = logging.getLogger(__name__)


class ProjectRevisionsApiView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    @method_permission_classes((UserHasReadAccess,))
    def get(self, request, *args, **kwargs):
        project: Project = self.get_object()
        serializer = self.get_serializer(project, context={"user": request.user})

        commits = None
        with contextlib.suppress(ValueError):
            # Checkout default branch and pull repository
            project.git_repo.checkout_default_branch()

            # Collect all the commits and sort them by date
            # Order: from most recent to oldest
            commits_serializer = CommitListSerializer(
                project.git_repo.commits, context={"project": project}
            )

            commits = commits_serializer.data

        try:
            return SuccessResponse({"project": serializer.data, "commits": commits})

        except GitlabError:
            logger.exception("There has been a problem accessing gitlab")
            return ErrorResponse(
                {"error": "There has been a problem accessing gitlab"},
                status=status.HTTP_400_BAD_REQUEST,
            )
