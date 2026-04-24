# -*- coding: utf-8 -*-

from __future__ import annotations

import io
import json
import logging
import re
from typing import TYPE_CHECKING
from typing import Any

import xlsxwriter
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from geojson import FeatureCollection  # type: ignore[attr-defined]
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.serializers import ValidationError

from speleodb.api.v2.permissions import IsObjectDeletion
from speleodb.api.v2.permissions import IsObjectEdition
from speleodb.api.v2.permissions import IsReadOnly
from speleodb.api.v2.permissions import SDB_AdminAccess
from speleodb.api.v2.permissions import SDB_ReadAccess
from speleodb.api.v2.permissions import SDB_WriteAccess
from speleodb.api.v2.serializers import ExperimentRecordGISSerializer
from speleodb.api.v2.serializers import ExperimentRecordSerializer
from speleodb.api.v2.serializers import ExperimentSerializer
from speleodb.gis.models import Experiment
from speleodb.gis.models import ExperimentRecord
from speleodb.gis.models import ExperimentUserPermission
from speleodb.gis.models import Station
from speleodb.gis.models import SubSurfaceStation
from speleodb.gis.models.experiment import MandatoryFieldUuid
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import DownloadResponseFromBlob
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import NoWrapResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from typing import Any

    from django.http import FileResponse
    from rest_framework.request import Request

    from speleodb.surveys.models import Project

logger = logging.getLogger(__name__)


class ExperimentApiView(GenericAPIView[Experiment], SDBAPIViewMixin):
    queryset = Experiment.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ExperimentSerializer

    def _handle_constraint_error(
        self, error: DjangoValidationError | ValidationError
    ) -> Response:
        """Handle database constraint violations and return user-friendly errors."""
        error_message = str(error)
        constraint_name = None

        # Handle ValidationError from Django's full_clean() (CheckConstraint violations)
        # Also handle serializers.ValidationError from serializer validation
        if isinstance(error, (DjangoValidationError, ValidationError)):
            # Check if this is an experiment_fields validation error
            # (not a constraint error)
            # DRF ValidationError uses .detail, Django ValidationError uses .error_dict
            error_data: dict[str, Any] | None = None
            if isinstance(error, ValidationError) and hasattr(error, "detail"):
                # DRF ValidationError
                if (
                    isinstance(error.detail, dict)
                    and "experiment_fields" in error.detail
                ):
                    # Type ignore: error.detail can be dict[str, Any] for DRF
                    error_data = error.detail
            elif (
                hasattr(error, "error_dict") and "experiment_fields" in error.error_dict  # pyright: ignore[reportAttributeAccessIssue]
            ):
                # Django ValidationError
                error_data = error.error_dict  # pyright: ignore[reportAttributeAccessIssue]

            if error_data:
                # This is a field immutability error, return it as-is
                return ErrorResponse(
                    {"errors": error_data},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if it's a constraint violation
            # DRF ValidationError uses .detail, Django ValidationError uses .error_dict
            constraint_error_dict: dict[str, Any] | None = None
            if isinstance(error, ValidationError) and hasattr(error, "detail"):
                if isinstance(error.detail, dict) and "__all__" in error.detail:
                    constraint_error_dict = error.detail
            elif hasattr(error, "error_dict") and "__all__" in error.error_dict:  # pyright: ignore[reportAttributeAccessIssue]
                constraint_error_dict = error.error_dict  # pyright: ignore[reportAttributeAccessIssue]

            if constraint_error_dict and "__all__" in constraint_error_dict:
                all_errors = constraint_error_dict["__all__"]
                for err in all_errors:
                    error_str = str(err)
                    # Extract constraint name from error message like:
                    # "Constraint "start_date_lte_end_date" is violated."
                    if "constraint" in error_str.lower():
                        error_message = error_str
                        # Try to extract constraint name from the message
                        match = re.search(r'Constraint\s+"([^"]+)"', error_str)
                        if match:
                            constraint_name = match.group(1)

        # Map constraint names to user-friendly error messages
        constraint_messages = {
            "end_date_requires_start_date": {
                "end_date": [
                    "If end_date is provided, start_date must also be provided."
                ]
            },
            "start_date_lte_end_date": {
                "end_date": ["end_date must be greater than or equal to start_date."],
            },
        }

        # Check which constraint was violated
        # First try the extracted constraint name, then fall back to string matching
        if constraint_name and constraint_name in constraint_messages:
            return ErrorResponse(
                {"errors": constraint_messages[constraint_name]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for constraint_name_key, error_dict in constraint_messages.items():
            if constraint_name_key in error_message:
                return ErrorResponse(
                    {"errors": error_dict}, status=status.HTTP_400_BAD_REQUEST
                )

        # Generic constraint error if we can't identify the specific constraint
        logger.exception("Unhandled constraint violation: %s", error_message)
        return ErrorResponse(
            {
                "errors": {
                    "non_field_errors": [
                        "This operation violates a database constraint. "
                        "Please check your input data."
                    ]
                }
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    @extend_schema(operation_id="v2_experiments_list")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()

        # Build the list of active experiments AND a per-id level map in a
        # single DB round trip. The map is passed to the serializer via
        # context so can_write/can_delete resolve without per-object queries
        # (avoids N+1 inside SerializerMethodField). Swap the previous
        # prefetch_related("experiment") for select_related: it's a
        # many-to-one FK, so a JOIN is the correct load strategy.
        experiments: list[Experiment] = []
        levels_by_id: dict[Any, int] = {}
        for perm in ExperimentUserPermission.objects.filter(
            user=user, is_active=True
        ).select_related("experiment"):
            experiment = perm.experiment
            if experiment.is_active:
                levels_by_id[experiment.id] = perm.level
                experiments.append(experiment)

        context = self.get_serializer_context()
        context["experiment_levels_by_id"] = levels_by_id
        serializer = self.get_serializer(experiments, many=True, context=context)

        return SuccessResponse(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()

        # Create a mutable copy of request.data
        data = (
            request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        )
        data["created_by"] = user.email

        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            try:
                serializer.save()
                return SuccessResponse(serializer.data, status=status.HTTP_201_CREATED)
            except (DjangoValidationError, ValidationError) as e:
                return self._handle_constraint_error(e)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class ExperimentSpecificApiView(GenericAPIView[Experiment], SDBAPIViewMixin):
    queryset = Experiment.objects.all()
    permission_classes = [
        (IsObjectDeletion & SDB_AdminAccess)
        | (IsObjectEdition & SDB_WriteAccess)
        | (IsReadOnly & SDB_ReadAccess)
    ]
    serializer_class = ExperimentSerializer
    lookup_field = "id"

    def _handle_constraint_error(
        self, error: DjangoValidationError | ValidationError
    ) -> Response:
        """Handle database constraint violations and return user-friendly errors."""
        error_message = str(error)
        constraint_name = None

        # Handle ValidationError from Django's full_clean() (CheckConstraint violations)
        # Also handle serializers.ValidationError from serializer validation
        if isinstance(error, (DjangoValidationError, ValidationError)):
            # Check if this is an experiment_fields validation error
            # (not a constraint error)
            # DRF ValidationError uses .detail, Django ValidationError uses .error_dict
            error_data: dict[str, Any] | None = None
            if isinstance(error, ValidationError) and hasattr(error, "detail"):
                # DRF ValidationError
                if (
                    isinstance(error.detail, dict)
                    and "experiment_fields" in error.detail
                ):
                    # Type ignore: error.detail can be dict[str, Any] for DRF
                    error_data = error.detail
            elif (
                hasattr(error, "error_dict") and "experiment_fields" in error.error_dict  # pyright: ignore[reportAttributeAccessIssue]
            ):
                # Django ValidationError
                error_data = error.error_dict  # pyright: ignore[reportAttributeAccessIssue]

            if error_data:
                # This is a field immutability error, return it as-is
                return ErrorResponse(
                    {"errors": error_data},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if it's a constraint violation
            # DRF ValidationError uses .detail, Django ValidationError uses .error_dict
            constraint_error_dict: dict[str, Any] | None = None
            if isinstance(error, ValidationError) and hasattr(error, "detail"):
                if isinstance(error.detail, dict) and "__all__" in error.detail:
                    constraint_error_dict = error.detail
            elif hasattr(error, "error_dict") and "__all__" in error.error_dict:  # pyright: ignore[reportAttributeAccessIssue]
                constraint_error_dict = error.error_dict  # pyright: ignore[reportAttributeAccessIssue]

            if constraint_error_dict and "__all__" in constraint_error_dict:
                all_errors = constraint_error_dict["__all__"]
                for err in all_errors:
                    error_str = str(err)
                    # Extract constraint name from error message like:
                    # "Constraint "start_date_lte_end_date" is violated."
                    if "constraint" in error_str.lower():
                        error_message = error_str
                        # Try to extract constraint name from the message
                        match = re.search(r'Constraint\s+"([^"]+)"', error_str)
                        if match:
                            constraint_name = match.group(1)

        # Map constraint names to user-friendly error messages
        constraint_messages = {
            "end_date_requires_start_date": {
                "end_date": [
                    "If end_date is provided, start_date must also be provided."
                ]
            },
            "start_date_lte_end_date": {
                "end_date": ["end_date must be greater than or equal to start_date."],
            },
        }

        # Check which constraint was violated
        # First try the extracted constraint name, then fall back to string matching
        if constraint_name and constraint_name in constraint_messages:
            return ErrorResponse(
                {"errors": constraint_messages[constraint_name]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for constraint_name_key, error_dict in constraint_messages.items():
            if constraint_name_key in error_message:
                return ErrorResponse(
                    {"errors": error_dict}, status=status.HTTP_400_BAD_REQUEST
                )

        # Generic constraint error if we can't identify the specific constraint
        logger.exception("Unhandled constraint violation: %s", error_message)
        return ErrorResponse(
            {
                "errors": {
                    "non_field_errors": [
                        "This operation violates a database constraint. "
                        "Please check your input data."
                    ]
                }
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Retrieve a specific experiment."""
        experiment = self.get_object()
        serializer = self.get_serializer(experiment)
        return SuccessResponse(serializer.data)

    def _modify_obj(
        self, request: Request, partial: bool, *args: Any, **kwargs: Any
    ) -> Response:
        experiment = self.get_object()
        serializer = self.get_serializer(experiment, data=request.data, partial=partial)

        if serializer.is_valid():
            try:
                serializer.save()
                return SuccessResponse(serializer.data)
            except (DjangoValidationError, ValidationError) as e:
                return self._handle_constraint_error(e)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._modify_obj(request=request, partial=False, **kwargs)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._modify_obj(request=request, partial=True, **kwargs)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Deactivate an experiment instead of deleting it.

        Sets is_active=False to deactivate the experiment while preserving
        all data and maintaining referential integrity.
        """
        user = self.get_user()
        experiment = self.get_object()

        for perm in experiment.user_permissions.all():
            perm.deactivate(deactivated_by=user)

        experiment.is_active = False
        experiment.save()

        return SuccessResponse(
            {"id": str(experiment.id), "message": "Experiment deactivated"}
        )


class ExperimentRecordApiView(GenericAPIView[Station], SDBAPIViewMixin):
    """List or create experiment records for a (station, experiment) pair.

    Permission contract is intentionally split across two layers because two
    distinct objects must each be authorized:

      - **station** (URL ``id``): class-level :class:`SDB_ReadAccess` enforces
        the caller can see the station at all. Resolved by ``get_object()``
        and applied via DRF's standard object-permission machinery.
      - **experiment** (URL ``exp_id``): an inline ``SDB_WriteAccess`` check
        inside :meth:`post` requires write access on the experiment, traversed
        by the permission machinery to ``ExperimentUserPermission``. ``GET``
        only requires station READ + experiment READ via an inline
        ``SDB_ReadAccess`` check.

    DRF's permission framework runs object-level checks against
    ``get_object()`` only, so there is no clean way to express the second
    check declaratively on this view without doubling up URL routing. The
    inline check is therefore the authoritative gate for write access; the
    class-level station permission is a necessary precondition.

    The frontend mirrors this contract by reading
    :attr:`ExperimentSerializer.can_write` / ``can_delete`` for UI gating
    instead of any project / network heuristic. Future record-mutation
    endpoints should follow the same pattern.
    """

    queryset = Station.objects.all()
    permission_classes = [SDB_ReadAccess]
    lookup_field = "id"
    serializer_class = ExperimentRecordSerializer  # type: ignore[assignment]

    def _get_experiment(self, **kwargs: Any) -> Experiment | Response:
        """Resolve the target experiment from the URL or return a 400/404.

        Inactive experiments are rejected with 404: they are not exposed on
        the list endpoint, and the frontend filters them out, so allowing
        mutations against them through a direct URL would be a silent
        backdoor. Any future "read historical inactive data" requirement is
        a deliberate product decision, not a silent regression.
        """
        if not (experiment_id := kwargs.get("exp_id")):
            return ErrorResponse(
                {"error": "The URL parameter `exp_id` was not received."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            return Experiment.objects.get(id=experiment_id, is_active=True)
        except Experiment.DoesNotExist:
            return ErrorResponse(
                {"error": f"The Experiment `{experiment_id}` was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Retrieve all experiment records for a station & experiment combination."""
        match experiment_or_response := self._get_experiment(**kwargs):
            case Response():
                return experiment_or_response

            case Experiment():
                station = self.get_object()

                if not SDB_ReadAccess().has_object_permission(
                    request,  # type: ignore[arg-type]
                    self,
                    experiment_or_response,
                ):
                    return ErrorResponse(
                        {"detail": "Not authorized to perform this action."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                exp_records = ExperimentRecord.objects.filter(
                    station=station,
                    experiment=experiment_or_response,
                ).order_by("-creation_date")

                serializer = self.get_serializer(exp_records, many=True)
                return SuccessResponse(serializer.data)

            case _:
                raise TypeError(
                    f"Unexpected type received: {type(experiment_or_response)}"
                )

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Creates an experiment record for a given station & experiment."""

        match experiment_or_response := self._get_experiment(**kwargs):
            case Response():
                return experiment_or_response

            case Experiment():
                station = self.get_object()
                user = self.get_user()

                if not SDB_WriteAccess().has_object_permission(
                    request,  # type: ignore[arg-type]
                    self,
                    experiment_or_response,
                ):
                    return ErrorResponse(
                        {"detail": "Not authorized to perform this action."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                incoming = request.data
                if not isinstance(incoming, dict):
                    return ErrorResponse(
                        {"errors": {"data": ["Request body must be a JSON object."]}},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                data = incoming.copy()
                data[MandatoryFieldUuid.SUBMITTER_EMAIL.value] = user.email

                serializer = self.get_serializer(
                    data={
                        "experiment": experiment_or_response.id,
                        "station": station.id,
                        "data": data,
                    }
                )

                if serializer.is_valid():
                    serializer.save()
                    return SuccessResponse(
                        serializer.data, status=status.HTTP_201_CREATED
                    )

                return ErrorResponse(
                    {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
                )

            case _:
                raise TypeError(
                    f"Unexpected type received: {type(experiment_or_response)}"
                )


class ExperimentRecordSpecificApiView(
    GenericAPIView[ExperimentRecord], SDBAPIViewMixin
):
    """Edit or delete a single experiment record by id (PUT / PATCH / DELETE).

    Permission contract is **dual-gated**, despite ``permission_classes``
    only mentioning experiment-level access. Both gates apply:

      - **station READ** is required via the
        ``BaseAccessLevel.has_object_permission(ExperimentRecord)``
        traversal in :mod:`speleodb.api.v2.permissions`, which calls
        ``SDB_ReadAccess().has_object_permission(request, view, obj.station)``
        before evaluating the experiment-level check.
      - **experiment-level access** (WRITE for PUT / PATCH, ADMIN for
        DELETE) is required via the OR-of-permissions chain declared on
        ``permission_classes`` and resolved against the record's
        ``obj.experiment``.

    A user with experiment WRITE / ADMIN but no project access on the
    record's station is therefore rejected with 403, matching the POST
    behavior on :class:`ExperimentRecordApiView`. The contract is pinned
    by :class:`TestExperimentRecordDetailRequiresStationAccess` in
    ``test_experiment_records_api.py``.
    """

    queryset = ExperimentRecord.objects.all()
    permission_classes = [
        (IsObjectDeletion & SDB_AdminAccess) | (IsObjectEdition & SDB_WriteAccess)
    ]
    lookup_field = "id"
    serializer_class = ExperimentRecordSerializer

    def get_queryset(self) -> Any:
        """Only expose records whose experiment is still active.

        Matches the list/POST contract enforced via ``_get_experiment`` on
        ``ExperimentRecordApiView``. Editing or deleting records on a
        deactivated experiment returns 404 rather than silently mutating
        historical data.
        """
        return ExperimentRecord.objects.filter(experiment__is_active=True)

    def _update_obj(self, request: Request, *, partial: bool) -> Response:
        """
        Update a record's editable JSON data.

        Contract:
          - PUT (partial=False): the request body fully replaces ``data``.
            Any field omitted from the payload is removed from ``data``.
          - PATCH (partial=True): the request body is merged into the existing
            ``data``. Only the keys present in the payload are overwritten.

        In both modes the server-owned identity is preserved:
          - ``station`` and ``experiment`` stay bound to the existing record.
          - ``submitter_email`` is restored from the existing record (or the
            current user if unset historically) and cannot be spoofed.
        """
        exp_record = self.get_object()
        existing_data: dict[str, Any] = (
            dict(exp_record.data) if isinstance(exp_record.data, dict) else {}
        )

        incoming = request.data
        if not isinstance(incoming, dict):
            return ErrorResponse(
                {"errors": {"data": ["Request body must be a JSON object."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if partial:
            new_data: dict[str, Any] = {**existing_data, **incoming}
        else:
            new_data = dict(incoming)

        new_data[MandatoryFieldUuid.SUBMITTER_EMAIL.value] = existing_data.get(
            MandatoryFieldUuid.SUBMITTER_EMAIL.value,
            self.get_user().email,
        )

        serializer = self.get_serializer(
            exp_record,
            data={
                "experiment": exp_record.experiment_id,
                "station": exp_record.station_id,
                "data": new_data,
            },
            partial=partial,
        )

        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Replace a record's editable data while preserving server-owned fields."""
        return self._update_obj(request, partial=False)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Merge the payload into the record's data, preserving server-owned fields."""
        return self._update_obj(request, partial=True)

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete an experiment record for a given station & experiment."""
        exp_record = self.get_object()

        record_id = exp_record.id
        exp_record.delete()

        return SuccessResponse(
            {"id": str(record_id), "message": "Experiment Record deleted"}
        )


class ExperimentGISApiView(GenericAPIView[Experiment], SDBAPIViewMixin):
    """
    Simple view to get all experiment data as GeoJSON-compatible format.
    """

    queryset = Experiment.objects.all()
    permission_classes = [permissions.AllowAny]
    lookup_field = "gis_token"
    serializer_class = ExperimentRecordGISSerializer  # type: ignore[assignment]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        experiment = self.get_object()

        serializer = self.get_serializer(
            ExperimentRecord.objects.filter(experiment=experiment).order_by(
                "-creation_date"
            ),
            many=True,
        )

        return NoWrapResponse(FeatureCollection(serializer.data))  # type: ignore[no-untyped-call]


class ExperimentExportExcelApiView(GenericAPIView[Experiment], SDBAPIViewMixin):
    """
    Export experiment data to Excel format.
    """

    queryset = Experiment.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    serializer_class = ExperimentRecordSerializer  # type: ignore[assignment]

    def get(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Response | FileResponse:
        user = self.get_user()
        experiment = self.get_object()

        # Check if user has read access
        try:
            ExperimentUserPermission.objects.get(
                user=user,
                experiment=experiment,
                is_active=True,
            )
        except ExperimentUserPermission.DoesNotExist:
            return ErrorResponse(
                {"error": "You do not have permission to access this experiment"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get all records for this experiment
        records = (
            ExperimentRecord.objects.filter(experiment=experiment)
            .select_related("station")
            .order_by("creation_date")
        )

        # Create Excel file in memory
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Experiment Data")

        # Define formats
        header_format = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#4F46E5",
                "font_color": "white",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            }
        )

        cell_format = workbook.add_format({"border": 1, "valign": "top"})

        # Build headers from experiment fields
        headers = [
            "Project Name",
            "Project ID",
            "Station ID",
            "Station Name",
            "Longitude",
            "Latitude",
        ]

        # Sort ALL experiment fields by order (including mandatory fields)
        field_definitions = experiment.experiment_fields or {}

        # Convert field_definitions to list and sort by order
        all_fields = [
            (field_uuid, field_data)
            for field_uuid, field_data in field_definitions.items()
        ]
        all_fields.sort(key=lambda x: x[1].get("order", 999))

        field_uuids = [field_uuid for field_uuid, _ in all_fields]
        field_names = [field_data.get("name", "") for _, field_data in all_fields]
        headers.extend(field_names)

        # Write headers
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, header_format)
            # Auto-adjust column width based on header length
            worksheet.set_column(col_num, col_num, max(len(header) + 2, 12))

        # Write data rows
        row_num = 1
        for record in records:
            col_num = 0

            project: Project | None = (
                record.station.project
                if isinstance(record.station, SubSurfaceStation)
                else None
            )

            # Project Name
            worksheet.write(
                row_num, col_num, project.name if project else "", cell_format
            )
            col_num += 1

            # Project ID
            worksheet.write(
                row_num, col_num, str(project.id) if project else "", cell_format
            )
            col_num += 1

            # Station ID
            worksheet.write(row_num, col_num, str(record.station.id), cell_format)
            col_num += 1

            # Station Name
            worksheet.write(row_num, col_num, record.station.name, cell_format)
            col_num += 1

            # Longitude
            if record.station.longitude is not None:
                worksheet.write(row_num, col_num, record.station.longitude, cell_format)
            else:
                worksheet.write(row_num, col_num, "", cell_format)
            col_num += 1

            # Latitude
            if record.station.latitude is not None:
                worksheet.write(row_num, col_num, record.station.latitude, cell_format)
            else:
                worksheet.write(row_num, col_num, "", cell_format)
            col_num += 1

            # All experiment fields (sorted by order, including mandatory fields)
            record_data = record.data or {}
            for field_uuid in field_uuids:
                value = record_data.get(field_uuid, "")

                match value:
                    case None:
                        value = ""

                    case list() | dict():
                        # Convert complex types to JSON string
                        value = json.dumps(value)

                worksheet.write(row_num, col_num, str(value), cell_format)
                col_num += 1

            row_num += 1

        # Close workbook
        workbook.close()
        output.seek(0)

        # Generate filename with timestamp
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        experiment_name = experiment.name.replace(" ", "_")
        filename = f"{experiment_name}_data_{timestamp}.xlsx"

        return DownloadResponseFromBlob(obj=output, filename=filename, attachment=True)
