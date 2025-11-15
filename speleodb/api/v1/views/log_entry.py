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
from speleodb.api.v1.serializers.log_entry import LogEntrySerializer
from speleodb.gis.models import LogEntry
from speleodb.gis.models import Station
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rest_framework.request import Request
    from rest_framework.response import Response


class LogEntryApiView(GenericAPIView[Station], SDBAPIViewMixin):
    queryset = Station.objects.all()
    permission_classes = [
        StationUserHasWriteAccess | (IsReadOnly & StationUserHasReadAccess)
    ]
    lookup_field = "id"
    serializer_class = LogEntrySerializer  # type: ignore[assignment]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        station = self.get_object()

        serializer = LogEntrySerializer(station.log_entries, many=True)

        return SuccessResponse(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new resource."""
        station = self.get_object()
        user = self.get_user()

        serializer = LogEntrySerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Save with the station and created_by
                serializer.save(station=station, created_by=user.email)
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


class LogEntrySpecificApiView(GenericAPIView[LogEntry], SDBAPIViewMixin):
    queryset = LogEntry.objects.all().select_related("station", "station__project")
    permission_classes = [
        (IsObjectDeletion & StationUserHasAdminAccess)
        | (IsObjectEdition & StationUserHasWriteAccess)
        | (IsReadOnly & StationUserHasReadAccess)
    ]
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        log_entry = self.get_object()
        serializer = LogEntrySerializer(log_entry)

        return SuccessResponse(serializer.data)

    def _modify_obj(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        project = self.get_object()
        serializer = LogEntrySerializer(project, data=request.data, partial=partial)

        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._modify_obj(request, partial=False, **kwargs)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._modify_obj(request, partial=True, **kwargs)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        log_entry = self.get_object()

        # Backup object `id` before deletion
        log_id = log_entry.id

        # Delete associated files if they exist
        if attachment := log_entry.attachment:
            attachment.delete(save=False)

        # Delete object itsel
        log_entry.delete()

        return SuccessResponse({"id": str(log_id)})
