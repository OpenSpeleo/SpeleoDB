# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.serializers.gis_view import GISViewCreateUpdateSerializer
from speleodb.api.v1.serializers.gis_view import GISViewSerializer
from speleodb.gis.models import GISView
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response

logger = logging.getLogger(__name__)


class GISViewManagementListApiView(GenericAPIView[GISView], SDBAPIViewMixin):
    """
    Authenticated endpoints for managing user's GIS views.

    GET: List all GIS views owned by the current user
    POST: Create a new GIS view
    """

    queryset = GISView.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GISViewSerializer

    def get_queryset(self) -> Any:
        """Filter to only views owned by the current user."""
        user = self.get_user()
        return (
            GISView.objects.filter(owner=user)
            .prefetch_related("rel_view_projects__project")
            .order_by("-modified_date")
        )

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """List all GIS views for the authenticated user."""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return SuccessResponse(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new GIS view."""
        user = self.get_user()

        serializer = GISViewCreateUpdateSerializer(
            data=request.data, context={"user": user}
        )

        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)

        return ErrorResponse(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class GISViewManagementDetailApiView(GenericAPIView[GISView], SDBAPIViewMixin):
    """
    Authenticated endpoints for managing a specific GIS view.

    GET: Retrieve GIS view details
    PUT/PATCH: Update GIS view
    DELETE: Deactivate GIS view (soft delete)
    """

    queryset = GISView.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GISViewSerializer
    lookup_field = "id"

    def get_queryset(self) -> Any:
        """Filter to only views owned by the current user."""
        user = self.get_user()
        return GISView.objects.filter(owner=user).prefetch_related(
            "rel_view_projects__project"
        )

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Retrieve a specific GIS view."""
        gis_view = self.get_object()
        serializer = self.get_serializer(gis_view)
        return SuccessResponse(serializer.data)

    def _modify_obj(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        """Helper method for PUT and PATCH."""
        gis_view = self.get_object()
        user = self.get_user()

        serializer = GISViewCreateUpdateSerializer(
            gis_view,
            data=request.data,
            partial=partial,
            context={"user": user},
        )

        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Full update of a GIS view."""
        return self._modify_obj(request=request, partial=False, **kwargs)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Partial update of a GIS view."""
        return self._modify_obj(request=request, partial=True, **kwargs)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Deactivate a GIS view (soft delete)."""
        gis_view = self.get_object()
        gis_view_id = gis_view.id

        gis_view.delete()

        return SuccessResponse({"id": str(gis_view_id), "message": "GIS View deleted"})
