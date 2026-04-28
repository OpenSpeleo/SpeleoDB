# -*- coding: utf-8 -*-

"""OGC API - Features views scoped to a **User** (``user_token`` / ``key``).

The OGC contract is implemented in
:mod:`speleodb.api.v2.views.ogc_base`; this module only provides:

* :class:`ProjectUserOGCService` — the ``OGCFeatureService`` adapter
  that yields one OGC collection per project the token's owner can
  read;
* the non-OGC authenticated GeoJSON list endpoint
  (``ProjectAllProjectGeoJsonApiView``) and the per-project commit-list
  endpoint (``ProjectGeoJsonCommitsApiView``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar

from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework.authtoken.models import Token
from rest_framework.generics import GenericAPIView

from speleodb.api.v2.permissions import SDB_ReadAccess
from speleodb.api.v2.permissions import SDB_WebViewerAccess
from speleodb.api.v2.serializers import ProjectGeoJSONCommitSerializer
from speleodb.api.v2.serializers import ProjectWithGeoJsonSerializer
from speleodb.api.v2.views.gis_view import _build_typed_collection_meta
from speleodb.api.v2.views.gis_view import _load_collection_bbox
from speleodb.api.v2.views.gis_view import _load_feature_by_id
from speleodb.api.v2.views.gis_view import _load_geometry_groups_present
from speleodb.api.v2.views.gis_view import _load_normalized_features
from speleodb.api.v2.views.ogc_base import BaseOGCCollectionApiView
from speleodb.api.v2.views.ogc_base import BaseOGCCollectionItemsApiView
from speleodb.api.v2.views.ogc_base import BaseOGCCollectionsApiView
from speleodb.api.v2.views.ogc_base import BaseOGCConformanceApiView
from speleodb.api.v2.views.ogc_base import BaseOGCLandingPageApiView
from speleodb.api.v2.views.ogc_base import BaseOGCSingleFeatureApiView
from speleodb.api.v2.views.ogc_base import OGCCollectionMeta
from speleodb.api.v2.views.ogc_base import OGCFeatureService
from speleodb.gis.models import ProjectGeoJSON
from speleodb.gis.ogc_helpers import GEOMETRY_GROUPS_ORDERED
from speleodb.gis.ogc_helpers import filter_features_by_geometry_group
from speleodb.gis.ogc_helpers import parse_typed_collection_id
from speleodb.surveys.models import Project
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.exceptions import NotAuthorizedError
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.compat import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response

    from speleodb.users.models import User


# ---------------------------------------------------------------------------
# Non-OGC helpers / views
# ---------------------------------------------------------------------------


class BaseUserProjectGeoJsonApiView(SDBAPIViewMixin):
    def get_user_projects(self, user: User) -> QuerySet[Project]:
        """Return projects the user has access to with their geojsons.

        Uses ``select_related("commit", "project")`` on the prefetched
        geojsons so that ``geojson.commit_sha`` (= ``commit.id``) and
        ``geojson.project.name`` resolve without per-row N+1 queries
        (ws6b).
        """
        user_projects = [perm.project for perm in user.permissions]

        geojson_prefetch = Prefetch(
            "geojsons",
            queryset=ProjectGeoJSON.objects.select_related(
                "commit",
                "project",
            ).order_by("-commit__authored_date"),
        )

        return Project.objects.filter(
            id__in=[project.id for project in user_projects],
        ).prefetch_related(geojson_prefetch)


class ProjectAllProjectGeoJsonApiView(
    GenericAPIView[Project],
    BaseUserProjectGeoJsonApiView,
):
    """API view that returns raw GeoJSON data for every user's project."""

    queryset = Project.objects.all()
    permission_classes = [SDB_WebViewerAccess]
    serializer_class = ProjectWithGeoJsonSerializer

    @extend_schema(operation_id="v2_projects_geojson_list")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        projects = self.get_user_projects(user)
        serializer = self.get_serializer(projects, many=True)
        return SuccessResponse(serializer.data)


# ---------------------------------------------------------------------------
# OGCFeatureService for user-token-scoped projects
# ---------------------------------------------------------------------------


class ProjectUserOGCService(OGCFeatureService[Token]):
    """OGC feature service for projects the token's user can read.

    Same geometry-typed split as :class:`ProjectViewOGCService`: each
    accessible project's latest commit becomes up to two OGC
    collections (``<sha>_points`` / ``<sha>_lines``) — only groups
    actually present are listed. Permission is verified for every
    collection lookup so that a token whose underlying user lost
    access mid-session cannot continue to read the project's items.
    """

    service_title: ClassVar[str] = "SpeleoDB User OGC API"
    service_description: ClassVar[str] = (
        "OGC API - Features endpoint exposing every active GIS project "
        "the token owner is currently allowed to read. Each project "
        "appears as one collection per geometry type actually present "
        "(`<sha>_points`, `<sha>_lines`)."
    )
    cache_control: ClassVar[str] = "public, max-age=86400"

    def list_collections(self, scope: Token) -> list[OGCCollectionMeta]:
        user: User = scope.user
        # One collection per (accessible-project-latest-commit,
        # geometry_group) tuple actually present. Per-collection bbox
        # is deferred to /collections/{id}; see
        # ProjectViewOGCService.list_collections for the rationale.
        helper = BaseUserProjectGeoJsonApiView()
        projects = helper.get_user_projects(user)
        out: list[OGCCollectionMeta] = []
        for project in projects:
            geojsons = list(project.geojsons.all())
            if not geojsons:
                continue
            latest = geojsons[0]
            present = _load_geometry_groups_present(latest.commit_sha)
            for group in GEOMETRY_GROUPS_ORDERED:
                if group not in present:
                    continue
                out.append(
                    _build_typed_collection_meta(
                        project_name=latest.project.name,
                        commit_sha=latest.commit_sha,
                        group=group,
                        bbox=None,
                    )
                )
        return out

    def get_collection(
        self,
        scope: Token,
        collection_id: str,
    ) -> OGCCollectionMeta | None:
        # Same SHA case-normalisation contract as ProjectViewOGCService:
        # ``parse_typed_collection_id`` lower-cases the SHA half so the
        # ORM lookup is canonical regardless of how the user-typed URL
        # was cased.
        parsed = parse_typed_collection_id(collection_id)
        if parsed is None:
            return None
        sha, group = parsed
        user: User = scope.user
        try:
            project_geojson = ProjectGeoJSON.objects.select_related(
                "project",
                "commit",
            ).get(commit__id=sha)
        except ProjectGeoJSON.DoesNotExist:
            return None
        try:
            user.get_best_permission(project_geojson.project)
        except NotAuthorizedError:
            # Treat permission denial as "not found" — never leak the
            # existence of resources outside the user's read scope.
            return None
        if group not in _load_geometry_groups_present(sha):
            # SHA exists and the user is permitted, but this geometry
            # group has no features at this commit — surface as 404
            # so QGIS / ArcGIS Pro do not add an empty layer.
            return None
        return _build_typed_collection_meta(
            project_name=project_geojson.project.name,
            commit_sha=sha,
            group=group,
            bbox=_load_collection_bbox(sha, group),
        )

    def get_features(
        self,
        scope: Token,
        collection_id: str,
    ) -> list[dict[str, Any]]:
        # Authorization performed in get_collection() — the generic
        # view always calls it first. The cached features list is
        # keyed by commit SHA only; the geometry filter is applied
        # at request time.
        parsed = parse_typed_collection_id(collection_id)
        if parsed is None:
            return []
        sha, group = parsed
        return filter_features_by_geometry_group(
            _load_normalized_features(sha),
            group,
        )

    def get_feature(
        self,
        scope: Token,
        collection_id: str,
        feature_id: str,
    ) -> dict[str, Any] | None:
        # O(1) lookup via the cached index then a constant-time group
        # filter — see ProjectViewOGCService.get_feature.
        parsed = parse_typed_collection_id(collection_id)
        if parsed is None:
            return None
        sha, group = parsed
        return _load_feature_by_id(sha, feature_id, group)

    def get_etag(self, scope: Token, collection_id: str) -> str | None:
        parsed = parse_typed_collection_id(collection_id)
        if parsed is None:
            return None
        sha, group = parsed
        return f"{sha}_{group}"


# ---------------------------------------------------------------------------
# OGC API - Features: User subclasses (public, token-based)
# ---------------------------------------------------------------------------


class OGCGISUserLandingPageApiView(BaseOGCLandingPageApiView):
    """OGC landing page for user-scoped projects."""

    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"
    service_class = ProjectUserOGCService


class OGCGISUserConformanceApiView(BaseOGCConformanceApiView):
    """OGC conformance declaration for user-scoped projects."""

    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"
    service_class = ProjectUserOGCService


class OGCGISUserProjectsApiView(BaseOGCCollectionsApiView):
    """OGC ``/collections`` list — every project accessible to the token."""

    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"
    service_class = ProjectUserOGCService


class OGCGISUserCollectionApiView(BaseOGCCollectionApiView):
    """OGC single-collection metadata for a user project."""

    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"
    service_class = ProjectUserOGCService


class OGCGISUserCollectionItemsApiView(BaseOGCCollectionItemsApiView):
    """OGC ``/items`` for a user project."""

    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"
    service_class = ProjectUserOGCService


class OGCGISUserSingleFeatureApiView(BaseOGCSingleFeatureApiView):
    """OGC ``/items/{featureId}`` for a user project."""

    queryset = Token.objects.select_related("user").all()
    lookup_field = "key"
    service_class = ProjectUserOGCService


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
    serializer_class = ProjectGeoJSONCommitSerializer  # type: ignore[assignment]
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        project = self.get_object()
        serializer = ProjectGeoJSONCommitSerializer(
            project.geojsons.order_by("-commit__authored_date"),
            many=True,
        )
        return SuccessResponse(serializer.data)
