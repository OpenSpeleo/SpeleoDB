# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import IsObjectDeletion
from speleodb.api.v1.permissions import IsObjectEdition
from speleodb.api.v1.permissions import IsReadOnly
from speleodb.api.v1.permissions import StationUserHasAdminAccess
from speleodb.api.v1.permissions import StationUserHasReadAccess
from speleodb.api.v1.permissions import StationUserHasWriteAccess
from speleodb.api.v1.serializers.station import StationResourceSerializer
from speleodb.surveys.models import Station
from speleodb.surveys.models import StationResource
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rest_framework.request import Request
    from rest_framework.response import Response


class StationResourceApiView(GenericAPIView[Station], SDBAPIViewMixin):
    queryset = Station.objects.all()
    permission_classes = [
        StationUserHasWriteAccess | (IsReadOnly & StationUserHasReadAccess)
    ]
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        station = self.get_object()

        serializer = StationResourceSerializer(
            station.rel_resources,
            many=True,
            context={"user": user},
        )

        return SuccessResponse(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new resource."""
        station = self.get_object()

        serializer = StationResourceSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Save with the station and created_by
                serializer.save(station=station, created_by=request.user)
                return SuccessResponse(
                    serializer.data,
                    status=status.HTTP_201_CREATED,
                )

            except ValidationError as e:
                # Convert model validation errors to API format
                errors: Mapping[str, Any] = {}
                if hasattr(e, "error_dict"):
                    errors = e.error_dict
                elif hasattr(e, "error_list"):
                    errors = {"non_field_errors": e.error_list}
                else:
                    errors = {"non_field_errors": [str(e)]}

                # Convert ErrorList to list of strings
                for field, error_list in errors.items():
                    errors[field] = [str(error) for error in error_list]  # type: ignore[misc]

                return ErrorResponse(
                    {"errors": errors}, status=status.HTTP_400_BAD_REQUEST
                )

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class StationResourceSpecificApiView(GenericAPIView[StationResource], SDBAPIViewMixin):
    queryset = StationResource.objects.all()
    permission_classes = [
        (IsObjectDeletion & StationUserHasAdminAccess)
        | (IsObjectEdition & StationUserHasWriteAccess)
        | (IsReadOnly & StationUserHasReadAccess)
    ]
    lookup_field = "id"

    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        user = self.get_user()
        station_resource = self.get_object()

        serializer = StationResourceSerializer(
            station_resource,
            context={"user": user},
        )

        return SuccessResponse(serializer.data)

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        project = self.get_object()
        serializer = StationResourceSerializer(
            project, data=request.data, context={"user": user}
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()
        station_resource = self.get_object()
        serializer = StationResourceSerializer(
            station_resource,
            data=request.data,
            context={"user": user},
            partial=True,
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        station_resource = self.get_object()

        # Backup object `id` before deletion
        resource_id = station_resource.id

        # Delete associated files if they exist
        if station_resource.file:
            station_resource.file.delete(save=False)

        if station_resource.miniature:
            station_resource.miniature.delete(save=False)

        # Delete object itsel
        station_resource.delete()

        return SuccessResponse({"id": str(resource_id)})
