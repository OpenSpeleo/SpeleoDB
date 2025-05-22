#!/usr/bin/env python
# -*- coding: utf-8 -*-

import contextlib
import logging
from typing import Any

from gitdb.exc import BadName as GitRevBadName
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.serializers import GitCommitListSerializer
from speleodb.api.v1.serializers import GitCommitSerializer
from speleodb.api.v1.serializers import GitFileListSerializer
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.git_engine.core import GitFile
from speleodb.git_engine.exceptions import GitBaseError
from speleodb.git_engine.exceptions import GitCommitNotFoundError
from speleodb.git_engine.gitlab_manager import GitlabError
from speleodb.surveys.models import Project
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

logger = logging.getLogger(__name__)


class ProjectRevisionsApiView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [UserHasReadAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        project: Project = self.get_object()
        serializer = self.get_serializer(project, context={"user": user})

        commits = None
        serialized_commits = []
        with contextlib.suppress(ValueError):
            # Checkout default branch and pull repository
            try:
                project.git_repo.checkout_default_branch()
                commits = list(project.git_repo.commits)
            except GitBaseError:
                commits = []

            # Collect all the commits and sort them by date
            # Order: from most recent to oldest
            commits_serializer = GitCommitListSerializer(
                commits, context={"project": project}
            )

            serialized_commits = commits_serializer.data

        try:
            return SuccessResponse(
                {"project": serializer.data, "commits": serialized_commits}
            )

        except GitlabError:
            logger.exception("There has been a problem accessing gitlab")
            return ErrorResponse(
                {"error": "There has been a problem accessing gitlab"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ProjectGitExplorerApiView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [UserHasReadAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def get(self, request: Request, hexsha: str, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        project: Project = self.get_object()
        try:
            # Checkout default branch and pull repository
            try:
                project.git_repo.checkout_default_branch()
            except GitBaseError:
                return ErrorResponse(
                    {"error": f"Problem checking out the commit `{hexsha}`"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

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

            # Important to be done last so that the repo is actualized
            project_serializer = self.get_serializer(
                project, context={"user": user, "n_commits": True}
            )

            return SuccessResponse(
                {
                    "project": project_serializer.data,
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
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except GitlabError:
            logger.exception("There has been a problem accessing gitlab")
            return ErrorResponse(
                {"error": "There has been a problem accessing gitlab"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
