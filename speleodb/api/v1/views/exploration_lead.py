# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from geojson import FeatureCollection  # type: ignore[attr-defined]
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import IsObjectCreation
from speleodb.api.v1.permissions import IsObjectDeletion
from speleodb.api.v1.permissions import IsObjectEdition
from speleodb.api.v1.permissions import IsReadOnly
from speleodb.api.v1.permissions import SDB_AdminAccess
from speleodb.api.v1.permissions import SDB_ReadAccess
from speleodb.api.v1.permissions import SDB_WriteAccess
from speleodb.api.v1.serializers.exploration_lead import (
    ExplorationLeadGeoJSONSerializer,
)
from speleodb.api.v1.serializers.exploration_lead import ExplorationLeadSerializer
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import ExplorationLead
from speleodb.surveys.models import Project
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import NoWrapResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response


class ProjectExplorationLeadsApiView(GenericAPIView[Project], SDBAPIViewMixin):
    """
    View to get all exploration leads for a project or create a new one.
    Similar pattern to ProjectStationsApiView.
    """

    queryset = Project.objects.all()
    permission_classes = [
        (IsObjectCreation & SDB_WriteAccess) | (IsReadOnly & SDB_ReadAccess)
    ]
    lookup_field = "id"
    serializer_class = ExplorationLeadSerializer  # type: ignore[assignment]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get all exploration leads that belong to the project."""
        project = self.get_object()
        serializer = ExplorationLeadSerializer(
            project.exploration_leads.all(),
            many=True,
        )
        return SuccessResponse(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new exploration lead for the project."""
        project = self.get_object()
        user = self.get_user()

        serializer = ExplorationLeadSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=user.email, project=project)

            return SuccessResponse(
                serializer.data,
                status=status.HTTP_201_CREATED,
            )

        return ErrorResponse(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ExplorationLeadSpecificApiView(GenericAPIView[ExplorationLead], SDBAPIViewMixin):
    """
    View to get, update, or delete a specific exploration lead.
    Similar pattern to StationSpecificApiView.
    """

    queryset = ExplorationLead.objects.all()
    permission_classes = [
        (IsObjectDeletion & SDB_AdminAccess)
        | (IsObjectEdition & SDB_WriteAccess)
        | (IsReadOnly & SDB_ReadAccess)
    ]
    lookup_field = "id"
    serializer_class = ExplorationLeadSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get exploration lead details."""
        lead = self.get_object()
        serializer = ExplorationLeadSerializer(lead)

        return SuccessResponse(serializer.data)

    def _modify_obj(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        """Helper to handle PUT and PATCH requests."""
        lead = self.get_object()
        serializer = ExplorationLeadSerializer(lead, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Full update of exploration lead."""
        return self._modify_obj(request=request, partial=False, **kwargs)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Partial update of exploration lead."""
        return self._modify_obj(request=request, partial=True, **kwargs)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete exploration lead."""
        lead = self.get_object()

        # Backup object `id` before deletion
        lead_id = lead.id

        # Delete object itself
        lead.delete()

        return SuccessResponse({"id": str(lead_id)})


class ProjectExplorationLeadsGeoJSONView(GenericAPIView[Project], SDBAPIViewMixin):
    """
    View to get all exploration leads for a project as GeoJSON-compatible data.
    Used by the map viewer to display lead markers.
    """

    queryset = Project.objects.all()
    permission_classes = [SDB_ReadAccess]
    lookup_field = "id"
    serializer_class = ExplorationLeadGeoJSONSerializer  # type: ignore[assignment]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get all exploration leads for a project in a map-friendly format."""
        project = self.get_object()

        leads = ExplorationLead.objects.filter(project=project)

        serializer = self.get_serializer(leads, many=True)

        return NoWrapResponse(FeatureCollection(serializer.data))  # type: ignore[no-untyped-call]


class AllExploLeadsGeoJSONApiView(GenericAPIView[ExplorationLead], SDBAPIViewMixin):
    """
    Simple view to get all stations for a user as GeoJSON-compatible data.
    Used by the map viewer to display station markers.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ExplorationLeadGeoJSONSerializer

    def get_queryset(self) -> QuerySet[ExplorationLead]:
        """Get only stations that the user has access to."""
        user = self.get_user()
        user_projects: list[Project] = [
            perm.project
            for perm in user.permissions
            if perm.level >= PermissionLevel.READ_ONLY
        ]
        return ExplorationLead.objects.filter(project__in=user_projects)

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get all stations for a user in a map-friendly format."""
        explo_leads = self.get_queryset()
        serializer = self.get_serializer(explo_leads, many=True)

        return NoWrapResponse(FeatureCollection(serializer.data))  # type: ignore[no-untyped-call]
