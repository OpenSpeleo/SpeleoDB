# -*- coding: utf-8 -*-

"""OGC API - Features views scoped to a **User** (``user_token`` / ``key``).

The OGC base classes live in :mod:`speleodb.api.v1.views.ogc_base`.
Each concrete class below sets ``queryset`` / ``lookup_field`` and
implements the one abstract getter that specialises it for the
user-token workflow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch
from django.http import Http404
from rest_framework.authtoken.models import Token
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import SDB_ReadAccess
from speleodb.api.v1.permissions import SDB_WebViewerAccess
from speleodb.api.v1.serializers import ProjectGeoJSONCommitSerializer
from speleodb.api.v1.serializers import ProjectWithGeoJsonSerializer
from speleodb.api.v1.views.ogc_base import BaseOGCCollectionApiView
from speleodb.api.v1.views.ogc_base import BaseOGCCollectionItemApiView
from speleodb.api.v1.views.ogc_base import BaseOGCCollectionsApiView
from speleodb.api.v1.views.ogc_base import BaseOGCConformanceApiView
from speleodb.api.v1.views.ogc_base import BaseOGCLandingPageApiView
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import Project
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.compat import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response
    from rest_framework.serializers import BaseSerializer

    from speleodb.users.models import User


# ---------------------------------------------------------------------------
# Non-OGC helpers / views
# ---------------------------------------------------------------------------


class BaseUserProjectGeoJsonApiView(SDBAPIViewMixin):
    def get_user_projects(self, user: User) -> QuerySet[Project]:
        """Restrict projects to those the current user has access to."""
        user_projects = [perm.project for perm in user.permissions]

        geojson_prefetch = Prefetch(
            "geojsons",
            queryset=ProjectGeoJSON.objects.order_by("-commit__authored_date"),
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
    permission_classes = [SDB_WebViewerAccess]
    serializer_class = ProjectWithGeoJsonSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        projects = self.get_user_projects(user)
        serializer = self.get_serializer(projects, many=True)
        return SuccessResponse(serializer.data)


# ---------------------------------------------------------------------------
# OGC API - Features: User subclasses (public, token-based)
# ---------------------------------------------------------------------------


class OGCGISUserLandingPageApiView(BaseOGCLandingPageApiView):
    """OGC landing page for user-scoped projects."""

    queryset = Token.objects.all()
    lookup_field = "key"


class OGCGISUserConformanceApiView(BaseOGCConformanceApiView):
    """OGC conformance declaration for user-scoped projects."""

    queryset = Token.objects.all()
    lookup_field = "key"


class OGCGISUserProjectsApiView(
    BaseOGCCollectionsApiView,
    BaseUserProjectGeoJsonApiView,
):
    """OGC ``/collections`` — lists all projects accessible to the token owner."""

    queryset = Token.objects.all()
    lookup_field = "key"

    def get_ogc_layer_data(self) -> list[dict[str, Any]]:
        token: Token = self.get_object()
        projects = self.get_user_projects(token.user)

        geojson_objs: list[ProjectGeoJSON] = [
            objs[0] for project in projects if (objs := project.geojsons.all())
        ]

        return [
            {
                "sha": geojson_obj.commit_sha,
                "title": geojson_obj.project.name,
                "description": f"Commit: {geojson_obj.commit_sha}",
                "url": geojson_obj.get_signed_download_url(expires_in=3600),
            }
            for geojson_obj in geojson_objs
        ]


class _UserCollectionMixin:
    """Shared ``get_geojson_object`` for the User collection endpoints."""

    def get_geojson_object(self, commit_sha: str) -> ProjectGeoJSON:
        token: Token = self.get_object()  # type: ignore[attr-defined]
        user: User = token.user

        try:
            project_geojson = ProjectGeoJSON.objects.select_related(
                "project", "commit"
            ).get(commit__id=commit_sha)
        except ProjectGeoJSON.DoesNotExist as e:
            raise Http404(
                f"ProjectGeoJSON with commit_sha '{commit_sha}' not found."
            ) from e

        project: Project = project_geojson.project

        try:
            _ = user.get_best_permission(project)
        except ObjectDoesNotExist as e:
            raise Http404(
                f"User does not have access to the project '{project}'."
            ) from e

        return project_geojson


class OGCGISUserCollectionApiView(_UserCollectionMixin, BaseOGCCollectionApiView):
    """OGC single-collection metadata for a user project."""

    queryset = Token.objects.all()
    lookup_field = "key"


class OGCGISUserCollectionItemApiView(
    _UserCollectionMixin,
    BaseOGCCollectionItemApiView,
):
    """OGC ``/items`` — proxy-served filtered GeoJSON for a user project."""

    queryset = Token.objects.all()
    lookup_field = "key"


# ---------------------------------------------------------------------------
# Non-OGC: commit listing
# ---------------------------------------------------------------------------


class ProjectGeoJsonCommitsApiView(GenericAPIView[Project], SDBAPIViewMixin):
    """List all ProjectGeoJSON commits for a project.

    Returns lightweight commit metadata without signed URLs.
    Used for populating commit selection dropdowns in UIs.
    """

    queryset = Project.objects.all()
    permission_classes = [SDB_ReadAccess]
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        project = self.get_object()
        serializer = ProjectGeoJSONCommitSerializer(
            project.geojsons.order_by("-commit__authored_date"),
            many=True,
        )
        return SuccessResponse(serializer.data)
