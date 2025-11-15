# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Experiment
from speleodb.gis.models import ExperimentRecord
from speleodb.gis.models import ExperimentUserPermission
from speleodb.gis.models.experiment import FieldType
from speleodb.gis.models.experiment import MandatoryFieldSlug
from speleodb.users.models import User


class ExperimentSerializer(serializers.ModelSerializer[Experiment]):
    """Serializer for Experiment model with field processing."""

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
                data["experiment_fields"] = self._convert_fields_list_to_dict(
                    fields_list
                )

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

    def _convert_fields_list_to_dict(
        self, value: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """
        Convert array of field objects to slug-based dictionary structure.

        Input format (from frontend):
        [
            {"name": "Measurement Date", "type": "date", "required": true},
            {"name": "Submitter Email", "type": "text", "required": true},
            {"name": "pH Level", "type": "number", "required": false, "options": [...]},
            ...
        ]

        Output format (for model):
        {
            "measurement_date": {"name": "Measurement Date", "type": "date", "required": true},
            "submitter_email": {"name": "Submitter Email", "type": "text", "required": true},
            "ph_level": {"name": "pH Level", "type": "number", "required": false, "options": [...]},
            ...
        }
        """  # noqa: E501
        # Always start with mandatory fields
        processed_fields = MandatoryFieldSlug.get_mandatory_fields().copy()
        existing_slugs = set(processed_fields.keys())

        if not value:
            # If no fields provided, return just mandatory fields
            return processed_fields

        # Process each field from the array
        for field_data in value:
            if not isinstance(field_data, dict):
                raise serializers.ValidationError(
                    {
                        "experiment_fields": [
                            "Each field must be a dictionary with 'name', 'type', and "
                            "'required' keys."
                        ]
                    }
                )

            field_name = field_data.get("name", "").strip()
            if not field_name:
                continue  # Skip empty fields

            field_type = field_data.get("type", "")
            field_required = field_data.get("required", False)
            field_options = field_data.get("options", [])

            # Validate field type
            if not field_type:
                raise serializers.ValidationError(
                    {
                        "experiment_fields": [
                            f"Field '{field_name}' is missing required 'type' field."
                        ]
                    }
                )

            if not FieldType.is_valid(field_type):
                valid_types = FieldType.get_all_types()
                raise serializers.ValidationError(
                    {
                        "experiment_fields": [
                            f"Invalid field type '{field_type}' for field "
                            f"'{field_name}'. Valid types: {', '.join(valid_types)}"
                        ]
                    }
                )

            # Check if this is a mandatory field (by name match)
            # Only check against mandatory field slugs, not all processed fields
            is_mandatory = False
            mandatory_fields = MandatoryFieldSlug.get_mandatory_fields()
            for mandatory_slug, mandatory_data in mandatory_fields.items():
                if mandatory_data["name"] == field_name:
                    is_mandatory = True
                    # Update mandatory field with provided data
                    # (if it exists in processed_fields)
                    if mandatory_slug in processed_fields:
                        processed_fields[mandatory_slug] = {
                            "name": field_name,
                            "type": field_type,
                            "required": field_required,
                        }
                    break

            if not is_mandatory:
                # Generate slug for custom field
                # Check both existing_slugs and processed_fields keys to ensure
                # uniqueness. This is critical for handling duplicate field names -
                # we need to check all slugs that have been generated so far
                # (in both the set and dict)
                all_existing_slugs = existing_slugs.copy()
                all_existing_slugs.update(processed_fields.keys())
                slug = Experiment.generate_unique_slug(field_name, all_existing_slugs)
                # Add the new slug to existing_slugs immediately so next
                # iteration sees it
                existing_slugs.add(slug)

                # IMPORTANT: Always add the field with its unique slug as the key
                # This allows multiple fields with the same name but different slugs
                # (e.g., ph_level and ph_level_1 for duplicate "pH Level" fields)

                # Build field data
                processed_field_data = {
                    "name": field_name,
                    "type": field_type,
                    "required": field_required,
                }

                # Add options if field type is select
                if field_type == FieldType.SELECT.value:
                    if not field_options:
                        raise serializers.ValidationError(
                            {
                                "experiment_fields": [
                                    f"Field '{field_name}' is of type 'select' but "
                                    "has no options."
                                ]
                            }
                        )
                    processed_field_data["options"] = field_options
                elif field_options:
                    raise serializers.ValidationError(
                        {
                            "experiment_fields": [
                                f"Field '{field_name}' has options but type is "
                                f"'{field_type}'. Options are only valid for "
                                "'select' type fields."
                            ]
                        }
                    )

                processed_fields[slug] = processed_field_data

        # Ensure all mandatory fields are present (in case frontend didn't send them)
        for (
            mandatory_slug,
            mandatory_data,
        ) in MandatoryFieldSlug.get_mandatory_fields().items():
            if mandatory_slug not in processed_fields:
                processed_fields[mandatory_slug] = mandatory_data

        return processed_fields

    def validate_experiment_fields(
        self, value: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Validate experiment_fields dict structure."""
        # Value is already converted to dict format by to_internal_value
        # Just validate the structure here
        if not isinstance(value, dict):
            raise serializers.ValidationError("experiment_fields must be a dictionary.")

        return value

    def to_representation(self, instance: Experiment) -> dict[str, Any]:
        """Convert slug-based dictionary back to array format for API responses."""
        data = super().to_representation(instance)

        # Convert experiment_fields from dict to array format
        # Include slug in each field for reference
        if "experiment_fields" in data:
            experiment_fields = data["experiment_fields"]
            if isinstance(experiment_fields, dict) and experiment_fields:
                fields_array = []
                for slug, field_data in experiment_fields.items():
                    if isinstance(field_data, dict):
                        field_with_slug = field_data.copy()
                        field_with_slug["slug"] = slug  # Include slug for reference
                        fields_array.append(field_with_slug)
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
        - Existing fields cannot be removed or modified (enforced by model validation)
        - Only new fields can be added
        - If experiment_fields is provided, merge new fields with existing ones
        - For PUT (non-partial), check that no fields are removed
        """
        # Handle experiment_fields merging for updates
        # If experiment_fields was sent as empty list, it means "don't change"
        # so we skip processing and preserve existing fields
        if "experiment_fields" in validated_data:
            # Get existing fields from the instance
            existing_fields = (
                instance.experiment_fields.copy() if instance.experiment_fields else {}
            )

            # Get new fields from validated_data (already converted to dict format)
            # This dict contains fields converted from the incoming list
            new_fields_dict = validated_data["experiment_fields"]

            # For PUT (non-partial), if experiment_fields is provided and not empty,
            # check that all existing custom fields are present
            # (to detect removal attempts)
            # Empty list means "don't change fields", so we preserve existing ones
            # However, if the request contains ONLY new custom fields
            # (no overlap with existing custom fields),
            # we allow it (treating it as "add new fields, preserve existing")
            # But if it contains SOME existing custom fields but not all,
            # that's a removal attempt
            # Also, if the user sends mandatory fields explicitly
            # (indicating they want to update fields),
            # they must include all existing custom fields
            if not self.partial and new_fields_dict and existing_fields:
                existing_slugs = set(existing_fields.keys())
                new_slugs = set(new_fields_dict.keys())

                # Get mandatory field slugs
                # (these are always added by _convert_fields_list_to_dict)
                mandatory_slugs = set(MandatoryFieldSlug.get_all_slugs())

                # Get existing custom (non-mandatory) fields
                existing_custom_slugs = existing_slugs - mandatory_slugs
                new_custom_slugs = new_slugs - mandatory_slugs

                # If there are existing custom fields, check if they're all present
                if existing_custom_slugs:
                    # Check if there's any overlap between existing custom fields
                    # and new custom fields
                    custom_overlap = existing_custom_slugs & new_custom_slugs

                    # If there's overlap with custom fields
                    # (some existing custom fields are present),
                    # then ALL existing custom fields must be present.
                    # This prevents partial removal attempts.
                    # If there's NO overlap with custom fields, check:
                    # - If user sent new custom fields (new_custom_slugs is not empty),
                    #   allow it (add new, preserve existing)
                    # - If user sent only mandatory fields (new_custom_slugs is empty),
                    #   require all existing custom fields
                    if custom_overlap:
                        # Some existing custom fields are present,
                        # so ALL must be present
                        missing_custom_slugs = existing_custom_slugs - new_custom_slugs
                        if missing_custom_slugs:
                            missing_field_names = [
                                existing_fields[slug].get("name", slug)
                                for slug in missing_custom_slugs
                            ]
                            error_msg = (
                                f"Cannot remove existing fields: "
                                f"{', '.join(missing_field_names)}. "
                                "Fields are immutable once created. "
                                "You can only add new fields."
                            )
                            raise serializers.ValidationError(
                                {"experiment_fields": [error_msg]}
                            )
                    elif not new_custom_slugs:
                        # No overlap and no new custom fields means
                        # user sent only mandatory fields
                        # In this case, they must include all existing custom fields
                        missing_field_names = [
                            existing_fields[slug].get("name", slug)
                            for slug in existing_custom_slugs
                        ]
                        error_msg = (
                            f"Cannot remove existing fields: "
                            f"{', '.join(missing_field_names)}. "
                            "Fields are immutable once created. "
                            "You can only add new fields."
                        )
                        raise serializers.ValidationError(
                            {"experiment_fields": [error_msg]}
                        )
                    # If no overlap but new_custom_slugs is not empty,
                    # user sent only new custom fields
                    # This is allowed (existing will be preserved by merge)

            # Merge: start with existing fields, then add/update with new fields
            # The model's immutability validation will catch any modifications
            merged_fields = existing_fields.copy()

            # Add all fields from new_fields_dict
            # If a slug already exists, the model validation will catch modifications
            # If it's a new slug, it will be added
            for slug, field_data in new_fields_dict.items():
                merged_fields[slug] = field_data

            validated_data["experiment_fields"] = merged_fields

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

    def validate(self, attrs: dict[str, str]) -> dict[str, str]:
        created_by = attrs.get("created_by")

        if self.instance is None and created_by is None:
            raise serializers.ValidationError(
                "`created_by` must be specified during creation."
            )

        if self.instance is not None and "created_by" in attrs:
            raise serializers.ValidationError("`created_by` cannot be updated.")

        return attrs


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
                "id": str(instance.id),
                "created_by": instance.created_by,
                **instance.data,
            },
        }
