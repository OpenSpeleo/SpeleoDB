# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db.models import Prefetch
from rest_framework import permissions
from rest_framework.authtoken.models import Token
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import ProjectUserHasReadAccess
from speleodb.api.v1.permissions import ProjectUserHasWebViewerAccess
from speleodb.api.v1.serializers import ProjectGeoJSONCommitSerializer
from speleodb.api.v1.serializers import ProjectWithGeoJsonSerializer
from speleodb.api.v1.views.utils import project_geojsons_to_proxied_response
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import Project
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from typing import Any

    from django.http import StreamingHttpResponse
    from rest_framework.compat import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response
    from rest_framework.serializers import BaseSerializer

    from speleodb.users.models import User

logger = logging.getLogger(__name__)


class BaseUserProjectGeoJsonApiView(SDBAPIViewMixin):
    def get_user_projects(self, user: User) -> QuerySet[Project]:
        """Restrict projects to those the current user has access to."""
        user_projects = [perm.project for perm in user.permissions]

        geojson_prefetch = Prefetch(
            "rel_geojsons", queryset=ProjectGeoJSON.objects.order_by("-commit_date")
        )

        return Project.objects.filter(
            id__in=[project.id for project in user_projects]
        ).prefetch_related(geojson_prefetch)


class ProjectAllProjectGeoJsonApiView(
    GenericAPIView[Project],
    BaseUserProjectGeoJsonApiView,
):
    """API view that returns raw GeoJSON data for every user's project."""

    queryset = Project.objects.all()
    permission_classes = [ProjectUserHasWebViewerAccess]
    serializer_class = ProjectWithGeoJsonSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Return all accessible projects and their GeoJSON data."""
        user = self.get_user()
        projects = self.get_user_projects(user)

        serializer = self.get_serializer(projects, many=True)
        return SuccessResponse(serializer.data)


class ProjectAllProjectGeoJsonGISApiView(
    GenericAPIView[Token], BaseUserProjectGeoJsonApiView
):
    """API view that returns raw GeoJSON data for every user's project in a proxied
    fashion for GIS."""

    queryset = Token.objects.all()
    permission_classes = [permissions.AllowAny]
    lookup_field = "key"

    def get_serializer(self, *args: Any, **kwargs: Any) -> BaseSerializer[Token]:
        return super().get_serializer(*args, **kwargs)

    def get(self, request: Request, *args: Any, **kwargs: Any) -> StreamingHttpResponse:
        """Return all accessible projects and their GeoJSON data."""
        token = self.get_object()
        projects = self.get_user_projects(token.user)

        geojson_objs: list[ProjectGeoJSON] = [
            objs[0] for project in projects if (objs := project.rel_geojsons.all())
        ]
        return project_geojsons_to_proxied_response(geojson_objs)


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
