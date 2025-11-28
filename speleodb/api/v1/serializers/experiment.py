# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from rest_framework import serializers
from rest_framework.fields import Field as DRFField

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Experiment
from speleodb.gis.models import ExperimentRecord
from speleodb.gis.models import ExperimentUserPermission
from speleodb.gis.models.experiment import ExperimentFieldDefinition
from speleodb.gis.models.experiment import MandatoryFieldUuid
from speleodb.users.models import User

logger = logging.getLogger(__name__)


class ExperimentFieldsField(DRFField):  # type: ignore[type-arg]
    """
    Custom field that accepts both list (API format) and dict (internal format).
    Does minimal validation here - actual validation happens in to_internal_value.
    """

    def to_internal_value(self, data: Any) -> Any:
        """Accept list or dict, return as-is for processing in serializer."""
        # Accept both list and dict - validation happens in serializer
        if isinstance(data, (list, dict)):
            return data
        raise serializers.ValidationError("Must be a list or dictionary.")

    def to_representation(self, value: Any) -> Any:
        """Return the value as-is - serializer handles conversion."""
        return value


class ExperimentSerializer(serializers.ModelSerializer[Experiment]):
    """Serializer for Experiment model with field processing."""

    # Use custom field that accepts both list (API) and dict (internal)
    experiment_fields = ExperimentFieldsField(required=False, allow_null=True)

    class Meta:
        model = Experiment
        fields = "__all__"
        read_only_fields = [
            "id",
            "created_by",
            "creation_date",
            "modified_date",
        ]

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert incoming list format to dict format before validation."""
        # Log what we received
        logger.debug(f"to_internal_value received: {type(data)}")
        if "experiment_fields" in data:
            logger.debug(
                f"experiment_fields type: {type(data.get('experiment_fields'))}"
            )
            logger.debug(f"experiment_fields value: {data.get('experiment_fields')}")

        # Handle experiment_fields conversion from list to dict
        if "experiment_fields" in data and isinstance(data["experiment_fields"], list):
            # Convert list to dict using validation logic
            data = data.copy()
            fields_list = data.pop("experiment_fields")

            # For updates, empty list means "don't change fields" - preserve existing
            # For creates, empty list means "only mandatory fields"
            if self.instance is not None and not fields_list:
                # This is an update and empty list was sent - skip conversion
                # We'll handle this in update() to preserve existing fields
                # Remove from data so it doesn't get processed
                # (we'll merge existing fields in update())
                pass  # Don't add experiment_fields back, update() will handle it
            else:
                # Create or non-empty list - convert normally
                # Pass existing fields if this is an update (for order calculation)
                existing_fields = (
                    self.instance.experiment_fields.copy()
                    if self.instance and self.instance.experiment_fields
                    else {}
                )
                try:
                    data["experiment_fields"] = self._convert_fields_list_to_dict(
                        fields_list, existing_fields
                    )
                except Exception:
                    logger.exception("Error in _convert_fields_list_to_dict")
                    raise

        # Handle empty date strings - convert to None for null=True fields
        # This allows empty strings to be treated as null/empty dates
        for date_field in ["start_date", "end_date"]:
            if date_field in data and data[date_field] == "":
                data[date_field] = None

        # Handle created_by - if provided in data, preserve it for create
        # (even though it's read_only, we need it for creation)
        if "created_by" in data and self.instance is None:
            # Store it temporarily so we can use it in create()
            self._created_by_from_data = data["created_by"]
        else:
            self._created_by_from_data = None

        return super().to_internal_value(data)  # type: ignore[no-any-return]

    def _validate_and_parse_field(
        self, field_data: dict[str, Any], field_name: str
    ) -> ExperimentFieldDefinition:
        """Validate and parse a single field using Pydantic."""
        if not isinstance(field_data, dict):
            raise serializers.ValidationError(
                {
                    "experiment_fields": [
                        "Each field must be a dictionary with 'name', 'type', and "
                        "'required' keys."
                    ]
                }
            )

        try:
            return ExperimentFieldDefinition(**field_data)
        except PydanticValidationError as e:
            # Convert Pydantic errors to DRF format
            errors = []
            for error in e.errors():
                field_path = " -> ".join(str(loc) for loc in error["loc"])
                error_msg = error["msg"]
                if field_path == "root":
                    errors.append(error_msg)
                else:
                    errors.append(f"{field_path}: {error_msg}")
            error_msg = f"Field '{field_name}': {', '.join(errors)}"
            raise serializers.ValidationError({"experiment_fields": [error_msg]}) from e
        except (ValueError, TypeError) as e:
            raise serializers.ValidationError(
                {"experiment_fields": [f"Field '{field_name}': {str(e)!s}"]}
            ) from e

    def _process_mandatory_field(
        self,
        field_def: ExperimentFieldDefinition,
        processed_fields: dict[str, dict[str, Any]],
    ) -> bool:
        """
        Process a mandatory field by name match. Returns True if processed.

        Note: The order should already be set correctly in field_def before calling
        this.
        """
        mandatory_fields = MandatoryFieldUuid.get_mandatory_fields()
        for mandatory_uuid, mandatory_data in mandatory_fields.items():
            if mandatory_data["name"] == field_def.name:
                if mandatory_uuid in processed_fields:
                    # Update the mandatory field with validated data
                    processed_fields[mandatory_uuid] = field_def.model_dump(
                        mode="json", exclude_none=True
                    )
                return True
        return False

    def _process_custom_field(
        self,
        field_def: ExperimentFieldDefinition,
        field_name: str,
        processed_fields: dict[str, dict[str, Any]],
        existing_uuids: set[str],
    ) -> None:
        """Process a custom (non-mandatory) field, generating a unique UUID."""
        # Generate a new UUID for the field
        field_uuid = Experiment.generate_field_uuid()
        existing_uuids.add(field_uuid)
        processed_fields[field_uuid] = field_def.model_dump(
            mode="json", exclude_none=True
        )

    def _ensure_mandatory_fields_present(
        self, processed_fields: dict[str, dict[str, Any]]
    ) -> None:
        """Ensure all mandatory fields are present in processed_fields."""
        for (
            mandatory_uuid,
            mandatory_data,
        ) in MandatoryFieldUuid.get_mandatory_fields().items():
            if mandatory_uuid not in processed_fields:
                processed_fields[mandatory_uuid] = mandatory_data

    def _convert_fields_list_to_dict(
        self, value: list[dict[str, Any]], existing_fields: dict[str, Any] | None = None
    ) -> dict[str, dict[str, Any]]:
        """
        Convert array of field objects to UUID-based dictionary structure.

        Array position determines order (implicit ordering).

        Args:
            value: List of field definitions from API request
            existing_fields: Existing fields from database (for validation)

        Input format (NEW):
        [
            {"id": "uuid-1", "name": "Measurement Date", "type": "date", "required": true},
            {"name": "pH Level", "type": "number", "required": false, "options": [...]},
            ...
        ]

        Output format (for model):
        {
            "uuid-1": {"name": "Measurement Date", "type": "date", "required": true, "order": 0},
            "<uuid>": {"name": "pH Level", "type": "number", "required": false, "order": 1, "options": [...]},
            ...
        }
        """  # noqa: E501
        # Start with empty dict for processing
        processed_fields: dict[str, dict[str, Any]] = {}
        existing_uuids = set()

        # Track which existing field IDs we've seen (for deletion detection)
        provided_field_ids = set()

        if not value:
            # If no fields provided, return just mandatory fields
            return MandatoryFieldUuid.get_mandatory_fields().copy()

        # Process each field from the array
        # Array index = order (for all fields provided in the array)
        for order, field_data in enumerate(value):
            # Validate field_data is a dict before processing
            if not isinstance(field_data, dict):
                raise serializers.ValidationError(
                    {
                        "experiment_fields": [
                            "Each field must be a dictionary. "
                            "New fields: {name, type, required}. "
                            "Existing fields: {id, name, type, required}."
                        ]
                    }
                )

            field_name = field_data.get("name", "").strip()
            if not field_name:
                continue  # Skip empty fields

            # Add order based on position in array (unless explicitly provided)
            field_data_with_order = field_data.copy()
            if "order" not in field_data_with_order:
                field_data_with_order["order"] = order

            # Validate and parse field using Pydantic (applies titlecase)
            field_def = self._validate_and_parse_field(
                field_data_with_order, field_name
            )

            # Check if ID is provided (for updates/reordering)
            # Support both "id" and "uuid" for backwards compatibility
            field_id = field_data.get("id") or field_data.get("uuid")

            if field_id:
                # Existing field - validate immutability rules
                provided_field_ids.add(field_id)

                # If we have existing_fields, validate that type/required haven't
                # changed
                if existing_fields and field_id in existing_fields:
                    existing_field = existing_fields[field_id]

                    # Check immutable properties
                    if existing_field.get("type") != field_def.type.value:
                        raise serializers.ValidationError(
                            {
                                "experiment_fields": [
                                    "Cannot change type of field "
                                    f"'{field_def.name}'. Type is immutable (was "
                                    f"'{existing_field.get('type')}', tried to change "
                                    f"to '{field_def.type.value}')."
                                ]
                            }
                        )

                    if existing_field.get("required") != field_def.required:
                        raise serializers.ValidationError(
                            {
                                "experiment_fields": [
                                    "Cannot change required status of field "
                                    f"'{field_def.name}'. Required status is immutable."
                                ]
                            }
                        )

                    # Check options immutability for SELECT fields
                    existing_options = existing_field.get("options")
                    new_options = field_def.options
                    if existing_options != new_options:
                        raise serializers.ValidationError(
                            {
                                "experiment_fields": [
                                    "Cannot change options of field "
                                    f"`{field_def.name}'. Options are immutable."
                                ]
                            }
                        )

                # Check for name conflicts with OTHER fields
                normalized_name = field_def.name.lower()
                for existing_id, existing_field in processed_fields.items():
                    if (
                        existing_id != field_id
                        and existing_field["name"].lower() == normalized_name
                    ):
                        raise serializers.ValidationError(
                            {
                                "experiment_fields": [
                                    f"Field name '{field_def.name}' is not unique. "
                                    "Another field with the same name already exists."
                                ]
                            }
                        )

                # Update the field with new order (from array position)
                processed_fields[field_id] = field_def.model_dump(
                    mode="json", exclude_none=True
                )
                existing_uuids.add(field_id)
            else:
                # New field (no ID provided)
                # Check if it matches a mandatory field by name
                mandatory_fields = MandatoryFieldUuid.get_mandatory_fields()
                is_mandatory = False

                for mandatory_uuid, mandatory_data in mandatory_fields.items():
                    if mandatory_data["name"] == field_def.name:
                        is_mandatory = True
                        provided_field_ids.add(mandatory_uuid)
                        processed_fields[mandatory_uuid] = field_def.model_dump(
                            mode="json", exclude_none=True
                        )
                        existing_uuids.add(mandatory_uuid)
                        break

                if not is_mandatory:
                    # Custom field - check name uniqueness against both processed and
                    # existing fields
                    normalized_name = field_def.name.lower()

                    # Check against fields already processed from request
                    for existing_field in processed_fields.values():
                        if existing_field["name"].lower() == normalized_name:
                            raise serializers.ValidationError(
                                {
                                    "experiment_fields": [
                                        f"Field name '{field_def.name}' is not unique. "
                                        "Another field with the same name already "
                                        "exists."
                                    ]
                                }
                            )

                    # Check against existing fields in database
                    if existing_fields:
                        for existing_field in existing_fields.values():
                            if (
                                existing_field.get("name", "").lower()
                                == normalized_name
                            ):
                                raise serializers.ValidationError(
                                    {
                                        "experiment_fields": [
                                            f"Field name '{field_def.name}' is not "
                                            "unique. Another field with the same name "
                                            "already exists."
                                        ]
                                    }
                                )

                    # Generate new UUID for custom field
                    new_uuid = Experiment.generate_field_uuid()
                    processed_fields[new_uuid] = field_def.model_dump(
                        mode="json", exclude_none=True
                    )
                    existing_uuids.add(new_uuid)

        # Handle partial vs full updates
        if existing_fields:
            is_partial = getattr(self, "partial", False)

            # Check if any field IDs were explicitly provided in the request
            any_ids_provided = len(provided_field_ids) > 0

            if any_ids_provided and not is_partial:
                # PUT with explicit field IDs: validate that ALL existing fields are
                # included. This prevents accidental removal of fields
                existing_field_ids = set(existing_fields.keys())
                missing_ids = existing_field_ids - provided_field_ids

                if missing_ids:
                    # Some existing fields were not included - this is an attempted
                    # removal
                    missing_names = [
                        existing_fields[field_id].get("name", field_id)
                        for field_id in missing_ids
                    ]
                    raise serializers.ValidationError(
                        {
                            "experiment_fields": [
                                "Cannot remove existing fields: "
                                f"{', '.join(missing_names)}. Fields are immutable "
                                "once created. Include all existing fields in PUT "
                                "requests."
                            ]
                        }
                    )

            # Merge provided fields with existing fields (additive)
            # This handles both PATCH and PUT with new-fields-only
            merged_fields = existing_fields.copy()
            merged_fields.update(processed_fields)
            processed_fields = merged_fields

        # Ensure all mandatory fields are present
        self._ensure_mandatory_fields_present(processed_fields)

        return processed_fields

    def validate_experiment_fields(
        self, value: dict[str, dict[str, Any]] | list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """
        Validate experiment_fields structure.

        Note: Should already be converted to dict by to_internal_value,
        but we accept both for safety.
        """
        # If it's still a list, it means to_internal_value didn't process it
        # This shouldn't happen in normal flow, but handle it gracefully
        if isinstance(value, list):
            # This would only happen if to_internal_value was bypassed somehow
            return value  # type: ignore[return-value]

        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "experiment_fields must be a list or dictionary."
            )

        return value

    def to_representation(self, instance: Experiment) -> dict[str, Any]:
        """
        Convert UUID-based dictionary back to array format for API responses.

        Array position represents order (implicit ordering).
        Fields are returned as: [{id, name, type, required, options}, ...]
        """
        data = super().to_representation(instance)

        # Convert experiment_fields from dict to array format
        if "experiment_fields" in data:
            experiment_fields = data["experiment_fields"]
            if isinstance(experiment_fields, dict) and experiment_fields:
                fields_array = []
                for field_uuid, field_data in experiment_fields.items():
                    if isinstance(field_data, dict):
                        # Create clean field representation
                        field_repr = {
                            "id": field_uuid,  # Use 'id' instead of 'uuid'
                            "name": field_data.get("name"),
                            "type": field_data.get("type"),
                            "required": field_data.get("required"),
                            "order": field_data.get("order", 0),
                        }
                        # Add options only if present (SELECT type)
                        if field_data.get("options"):
                            field_repr["options"] = field_data["options"]

                        fields_array.append(field_repr)

                # Sort by order field (internal), but don't expose order in output
                fields_array.sort(
                    key=lambda x: experiment_fields[x["id"]].get("order", 999)
                )
                data["experiment_fields"] = fields_array
            elif not experiment_fields:
                # Empty dict or None - return empty array
                data["experiment_fields"] = []

        return data

    def create(self, validated_data: dict[str, Any]) -> Experiment:
        """Create a new experiment with processed field definitions."""
        # experiment_fields is already converted to dict format by
        # `validate_experiment_fields`
        # Set created_by if it was provided in the original data
        if hasattr(self, "_created_by_from_data") and self._created_by_from_data:
            validated_data["created_by"] = self._created_by_from_data

        experiment = super().create(validated_data)

        _ = ExperimentUserPermission.objects.create(
            user=User.objects.get(email=validated_data["created_by"]),
            experiment=experiment,
            level=PermissionLevel.ADMIN,
        )

        return experiment

    def update(
        self, instance: Experiment, validated_data: dict[str, Any]
    ) -> Experiment:
        """
        Update an experiment, ensuring field immutability.

        When updating experiment_fields:
        - Existing field IDs cannot be removed
        (validated in _convert_fields_list_to_dict)
        - Field type, required, and options cannot be modified
        (validated in _convert_fields_list_to_dict)
        - Field name and order (via array position) CAN be modified
        - New fields can be added
        - Array position determines order
        """
        # The _convert_fields_list_to_dict already handles all validation
        # including deletion detection and immutability checks
        # Just apply the validated data
        return super().update(instance, validated_data)


class ExperimentRecordSerializer(serializers.ModelSerializer[ExperimentRecord]):
    """Serializer for Experiment model with field processing."""

    class Meta:
        model = ExperimentRecord
        fields = "__all__"
        read_only_fields = [
            "id",
            "creation_date",
            "modified_date",
        ]


class ExperimentRecordGISSerializer(serializers.Serializer[ExperimentRecord]):
    """Map serializer for POIs - returns GeoJSON-like format."""

    def to_representation(self, instance: ExperimentRecord) -> dict[str, Any]:
        """Convert to GeoJSON Feature format."""
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    float(instance.station.longitude),
                    float(instance.station.latitude),
                ],
            },
            "properties": {
                "station_id": str(instance.station.id),
                "station_name": instance.station.name,
                **instance.data,
            },
        }
