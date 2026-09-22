"""Read-only status of optional map generation, independent of source uploads."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView

from speleodb.api.v2.permissions import SDB_ReadAccess
from speleodb.api.v2.serializers.project import ProjectGeoJSONStatusSerializer
from speleodb.gis.models import ProjectGeoJSONGeneration
from speleodb.surveys.models import Project
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response


class ProjectGeoJSONStatusView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [SDB_ReadAccess]
    # Object permissions use Project; the response serializes derived status data.
    serializer_class = ProjectGeoJSONStatusSerializer  # type: ignore[assignment]
    lookup_field = "id"
    http_method_names = ["get", "head", "options"]

    @extend_schema(operation_id="v2_project_geojson_status")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        project = self.get_object()
        commit = project.latest_commit
        # An unrelated document upload must not hide an earlier survey job.
        generation = (
            ProjectGeoJSONGeneration.objects.filter(commit__project=project)
            .order_by("-commit__authored_date", "-commit__creation_date", "-commit_id")
            .first()
        )
        # Read status before artifacts: observing READY guarantees publication
        # committed already. The reverse order could freeze polling on stale data.
        artifact = project.geojsons.first()
        state = "not_requested"
        error_code: str | None = None
        error: str | None = None
        if project.exclude_geojson:
            state = "skipped"
            error_code = "excluded"
            error = "Map generation is disabled for this project."
        elif generation is not None:
            state = generation.state
            error_code = generation.last_error_code or None
            error = generation.last_error or None
        elif (
            artifact is not None
            and commit is not None
            and artifact.commit_id == commit.pk
        ):
            state = "ready"

        data = {
            "state": state,
            "source_commit_sha": commit.pk if commit is not None else None,
            "generation_commit_sha": generation.commit_id
            if generation is not None
            else None,
            "geojson_commit_sha": artifact.commit_id if artifact is not None else None,
            "geojson_revision": artifact.geojson_revision
            if artifact is not None
            else None,
            "error_code": error_code,
            "error": error,
            "updated_at": generation.updated_at if generation is not None else None,
        }
        return SuccessResponse(self.get_serializer(data).data)
