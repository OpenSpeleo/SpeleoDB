# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING
from typing import Any

import orjson
from django.db.models import Prefetch
from django.db.utils import IntegrityError
from django.http import StreamingHttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import ProjectUserHasAdminAccess
from speleodb.api.v1.permissions import ProjectUserHasReadAccess
from speleodb.api.v1.permissions import ProjectUserHasWebViewerAccess
from speleodb.api.v1.permissions import ProjectUserHasWriteAccess
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
    from collections.abc import Generator

    from rest_framework.compat import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response

logger = logging.getLogger(__name__)


class ProjectSpecificApiView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [ProjectUserHasReadAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    @extend_schema(operation_id="v1_project_retrieve")
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

    @method_permission_classes((ProjectUserHasWriteAccess,))
    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        project = self.get_object()
        serializer = self.get_serializer(
            project, data=request.data, context={"user": user}
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    @method_permission_classes((ProjectUserHasWriteAccess,))
    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        project = self.get_object()
        serializer = self.get_serializer(
            project, data=request.data, context={"user": user}, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    @method_permission_classes((ProjectUserHasAdminAccess,))
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
        serializer = self.get_serializer(
            [
                perm.project
                for perm in user.permissions
                if perm.level > PermissionLevel.WEB_VIEWER
            ],
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


class ProjectAllGeoJsonApiView(GenericAPIView[Project], SDBAPIViewMixin):
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


class ProjectGeoJsonApiView(GenericAPIView[Project], SDBAPIViewMixin):
    """API view that returns raw GeoJSON data for a project."""

    queryset = Project.objects.all()
    permission_classes = [ProjectUserHasWebViewerAccess]
    serializer_class = ProjectWithGeoJsonSerializer
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Return the raw GeoJSON data as JSON response."""
        # First check permissions by getting the object normally
        project = self.get_object()
        ordered_geojson_qs = project.rel_geojsons.order_by("-commit_date")

        # Build ordered queryset and apply optional limit
        limit_param = request.query_params.get("limit")

        limit_val = 1  # default limit value
        if limit_param is not None:
            # Ignore invalid limit values and return full list
            with contextlib.suppress(TypeError, ValueError):
                # limit_param in [1, 20]
                limit_val = min(20, max(1, int(limit_param)))

        project._geojson_files = ordered_geojson_qs[:limit_val]  # type: ignore[attr-defined]  # noqa: SLF001

        serializer = self.get_serializer(project)

        return SuccessResponse(serializer.data)


class ProjectGISGeoJsonApiView(GenericAPIView[Project], SDBAPIViewMixin):
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

    def get(self, request: Request, *args: Any, **kwargs: Any) -> StreamingHttpResponse:
        projects = self.get_queryset()

        geojson_objs: list[ProjectGeoJSON] = [
            objs[0] for project in projects if (objs := project.rel_geojsons.all())
        ]

        def generator() -> Generator[str]:
            yield '{"type":"FeatureCollection","features":['
            first = True
            for geo in geojson_objs:
                with geo.file.open("rb") as f:
                    data = orjson.loads(f.read())
                    for feature in data.get("features", []):
                        if not first:
                            yield ","
                        yield orjson.dumps(feature).decode("utf-8")
                        first = False
            yield "]}"

        return StreamingHttpResponse(generator(), content_type="application/geo+json")
