# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING
from typing import Any

import orjson
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch
from django.http import Http404
from django.http import StreamingHttpResponse
from rest_framework import permissions
from rest_framework.authtoken.models import Token
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import SDB_ReadAccess
from speleodb.api.v1.permissions import SDB_WebViewerAccess
from speleodb.api.v1.serializers import ProjectGeoJSONCommitSerializer
from speleodb.api.v1.serializers import ProjectWithGeoJsonSerializer
from speleodb.gis.models import ProjectGeoJSON
from speleodb.gis.ogc_models import OGCLayerList
from speleodb.surveys.models import Project
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import GISResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import Any

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
            "rel_geojsons",
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
        """Return all accessible projects and their GeoJSON data."""
        user = self.get_user()
        projects = self.get_user_projects(user)

        serializer = self.get_serializer(projects, many=True)
        return SuccessResponse(serializer.data)


class OGCGISUserProjectsApiView(GenericAPIView[Token], BaseUserProjectGeoJsonApiView):
    """API view that returns raw GeoJSON data for every user's project in a proxied
    fashion for GIS."""

    queryset = Token.objects.all()
    permission_classes = [permissions.AllowAny]
    lookup_field = "key"

    def get_serializer(self, *args: Any, **kwargs: Any) -> BaseSerializer[Token]:
        return super().get_serializer(*args, **kwargs)

    def get(self, request: Request, *args: Any, **kwargs: Any) -> GISResponse:
        """Return all accessible projects and their GeoJSON data."""
        token = self.get_object()
        projects = self.get_user_projects(token.user)

        geojson_objs: list[ProjectGeoJSON] = [
            objs[0] for project in projects if (objs := project.rel_geojsons.all())
        ]

        data = [
            {
                "sha": geojson_obj.commit_sha,
                "title": geojson_obj.project.name,
                "description": f"Commit: {geojson_obj.commit_sha}",
                "url": geojson_obj.get_signed_download_url(expires_in=3600),
            }
            for geojson_obj in geojson_objs
        ]

        ogc_layers: OGCLayerList = OGCLayerList.model_validate({"layers": data})

        return GISResponse(ogc_layers.to_ogc_collections(request=request))


class BaseOGCGISViewCollectionApiView(GenericAPIView[Token], SDBAPIViewMixin):
    queryset = Token.objects.all()
    permission_classes = [permissions.AllowAny]
    lookup_field = "key"

    def get_geojson_object(self, commit_sha: str) -> ProjectGeoJSON:
        user: User = self.get_object().user

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


class OGCGISUserCollectionApiView(BaseOGCGISViewCollectionApiView):
    def get(
        self,
        request: Request,
        key: str,
        commit_sha: str,
        *args: Any,
        **kwargs: Any,
    ) -> GISResponse:
        """Return GeoJSON signed URLs for the view."""
        project_geojson = self.get_geojson_object(commit_sha=commit_sha)

        return GISResponse(
            {
                "id": project_geojson.id,
                "title": project_geojson.project.name,
                "description": f"Commit: {project_geojson.commit_sha}",
                "itemType": "feature",
                "links": [
                    {
                        "href": project_geojson.get_signed_download_url(
                            expires_in=3600
                        ),
                        "rel": "items",
                        "type": "application/geo+json",
                        "title": f"{project_geojson.project.name}",
                    }
                ],
            }
        )


class OGCGISUserCollectionItemApiView(BaseOGCGISViewCollectionApiView):
    def get(
        self,
        request: Request,
        key: str,
        commit_sha: str,
        *args: Any,
        **kwargs: Any,
    ) -> StreamingHttpResponse:
        project_geojson = self.get_geojson_object(commit_sha=commit_sha)

        buffer = BytesIO()

        cache_key = f"ogc_collections_project_geojson_{project_geojson.commit_sha}"
        cached_content: bytes | None = cache.get(cache_key)

        if cached_content:
            buffer.write(cached_content)
            buffer.seek(0)  # rewind to start

        else:

            def geojson_filter() -> bytes:
                with project_geojson.file.open("rb") as f:
                    features = orjson.loads(f.read()).get("features", [])

                    data = {
                        "type": "FeatureCollection",
                        "features": [
                            feature
                            for feature in features
                            if feature.get("geometry", {}).get("type") == "LineString"
                        ],
                    }

                return orjson.dumps(data)

            data: bytes = geojson_filter()
            buffer.write(data)
            buffer.seek(0)  # rewind to start

            # set cache 1 hour
            cache.set(
                cache_key,
                data,
                timeout=60 * 60,
            )

        def buffer_stream() -> Generator[bytes, Any]:
            chunk_size = 4096
            while chunk := buffer.read(chunk_size):
                yield chunk

        return StreamingHttpResponse(
            buffer_stream(),
            content_type="application/geo+json",
        )


class ProjectGeoJsonCommitsApiView(GenericAPIView[Project], SDBAPIViewMixin):
    """
    API view to list all ProjectGeoJSON commits for a project.

    Returns lightweight commit metadata without signed URLs.
    Used for populating commit selection dropdowns in UIs.

    Requires READ_ONLY access or higher (excludes WEB_VIEWER).
    """

    queryset = Project.objects.all()
    permission_classes = [SDB_ReadAccess]
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Return list of commits with GeoJSON data."""

        project = self.get_object()

        # Get all GeoJSON for this project, ordered by commit_date descending
        serializer = ProjectGeoJSONCommitSerializer(
            project.rel_geojsons.order_by("-commit__authored_date"),
            many=True,
        )

        return SuccessResponse(serializer.data)
