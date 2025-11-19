# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING
from typing import Any

from django.db.models import Prefetch
from django.db.utils import IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import ProjectUserHasAdminAccess
from speleodb.api.v1.permissions import ProjectUserHasReadAccess
from speleodb.api.v1.permissions import ProjectUserHasWebViewerAccess
from speleodb.api.v1.permissions import ProjectUserHasWriteAccess
from speleodb.api.v1.serializers import ProjectGeoJSONCommitSerializer
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.serializers import ProjectWithGeoJsonSerializer
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import ProjectGeoJSON
from speleodb.git_engine.gitlab_manager import GitlabError
from speleodb.surveys.models import Project
from speleodb.utils.api_decorators import method_permission_classes
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.compat import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response

logger = logging.getLogger(__name__)


class ProjectAllProjectGeoJsonApiView(GenericAPIView[Project], SDBAPIViewMixin):
    """API view that returns raw GeoJSON data for a project."""

    queryset = Project.objects.all()
    permission_classes = [ProjectUserHasWebViewerAccess]
    serializer_class = ProjectWithGeoJsonSerializer

    def get_queryset(self) -> QuerySet[Project]:
        """Restrict projects to those the current user has access to."""
        user = self.get_user()
        user_projects = [perm.project for perm in user.permissions]

        geojson_prefetch = Prefetch(
            "rel_geojsons", queryset=ProjectGeoJSON.objects.order_by("-commit_date")
        )

        return Project.objects.filter(
            id__in=[project.id for project in user_projects]
        ).prefetch_related(geojson_prefetch)

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Return all accessible projects and their GeoJSON data."""
        limit_param = request.query_params.get("limit")

        # Default and validation for limit
        limit_val = 1
        if limit_param is not None:
            with contextlib.suppress(TypeError, ValueError):
                # limit_param in [1, 20]
                limit_val = min(20, max(1, int(limit_param)))

        projects = self.get_queryset()

        # Optionally slice GeoJSONs per project (in-memory since limit is small)
        for project in projects:
            project._geojson_files = (  # type: ignore[attr-defined]  # noqa: SLF001
                project.rel_geojsons.all()[:limit_val]
            )

        serializer = self.get_serializer(projects, many=True)

        return SuccessResponse(serializer.data)


class ProjectGeoJsonCommitsApiView(GenericAPIView[Project], SDBAPIViewMixin):
    """
    API view to list all ProjectGeoJSON commits for a project.

    Returns lightweight commit metadata without signed URLs.
    Used for populating commit selection dropdowns in UIs.

    Requires READ_ONLY access or higher (excludes WEB_VIEWER).
    """

    queryset = Project.objects.all()
    permission_classes = [ProjectUserHasReadAccess]
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Return list of commits with GeoJSON data."""

        project = self.get_object()

        # Get all GeoJSON for this project, ordered by commit_date descending
        serializer = ProjectGeoJSONCommitSerializer(
            project.rel_geojsons.order_by("-commit_date"),
            many=True,
        )

        return SuccessResponse(serializer.data)
