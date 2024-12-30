#!/usr/bin/env python
# -*- coding: utf-8 -*-

import contextlib
import logging

from gitdb.exc import BadName as GitRevBadName
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.serializers import GitCommitListSerializer
from speleodb.api.v1.serializers import GitCommitSerializer
from speleodb.api.v1.serializers import GitFileListSerializer
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.git_engine.core import GitFile
from speleodb.git_engine.exceptions import GitCommitNotFoundError
from speleodb.surveys.models import Project
from speleodb.utils.gitlab_manager import GitlabError
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

logger = logging.getLogger(__name__)


class ProjectRevisionsApiView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [UserHasReadAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def get(self, request, *args, **kwargs):
        project: Project = self.get_object()
        serializer = self.get_serializer(project, context={"user": request.user})

        commits = None
        with contextlib.suppress(ValueError):
            # Checkout default branch and pull repository
            project.git_repo.checkout_default_branch()

            # Collect all the commits and sort them by date
            # Order: from most recent to oldest
            commits_serializer = GitCommitListSerializer(
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


class ProjectGitExplorerApiView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [UserHasReadAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def get(self, request, hexsha: str, *args, **kwargs):
        project: Project = self.get_object()
        serializer = self.get_serializer(project, context={"user": request.user})

        try:
            # Checkout default branch and pull repository
            project.git_repo.checkout_default_branch()

            commit = project.git_repo.commit(hexsha)

            # Collect all the commits and sort them by date
            # Order: from most recent to oldest
            commit_serializer = GitCommitSerializer(
                commit, context={"project": project}
            )

            file_serializer = GitFileListSerializer(
                [item for item in commit.tree.traverse() if isinstance(item, GitFile)],
                context={"project": project},
            )

            return SuccessResponse(
                {
                    "project": serializer.data,
                    "commit": commit_serializer.data,
                    "files": file_serializer.data,
                }
            )

        except (ValueError, GitCommitNotFoundError, GitRevBadName):
            logger.exception(
                f"There has been a problem checking out the commit `{hexsha}`"
            )
            return ErrorResponse(
                {"error": f"Problem checking out the commit `{hexsha}`"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except GitlabError:
            logger.exception("There has been a problem accessing gitlab")
            return ErrorResponse(
                {"error": "There has been a problem accessing gitlab"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
