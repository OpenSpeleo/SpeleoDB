# -*- coding: utf-8 -*-

from __future__ import annotations

import enum
import hashlib
import json
import logging
import uuid
from typing import TYPE_CHECKING
from typing import Annotated
from typing import Any
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CheckConstraint
from django.db.models import Q
from pydantic import BaseModel as PydanticBaseModel
from pydantic import BeforeValidator
from pydantic import Field
from pydantic import RootModel as PydanticRootModel
from pydantic import ValidationError as PydanticValidationError
from pydantic import field_validator
from pydantic import model_validator

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Station
from speleodb.gis.models.utils import generate_random_token
from speleodb.users.models import User
from speleodb.utils.pydantic_utils import pydantic_to_django_validation_error

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db.models.base import ModelBase
    from django_stubs_ext import StrOrPromise

logger = logging.getLogger(__name__)


class FieldType(enum.Enum):
    """Enumeration of valid field types for experiment data collection."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    SELECT = "select"

    @classmethod
    def get_all_types(cls) -> list[str]:
        """Return all field types as a list."""
        return [field_type.value for field_type in cls]

    @classmethod
    def is_valid(cls, field_type: str) -> bool:
        """Check if a field type is valid."""
        return field_type in cls.get_all_types()

    @classmethod
    def get_choices(cls) -> list[tuple[str, str]]:
        """Get choices for form dropdowns (value, display_name)."""
        display_names = {
            cls.TEXT: "Text",
            cls.NUMBER: "Number",
            cls.DATE: "Date",
            cls.BOOLEAN: "Yes/No",
            cls.SELECT: "Multiple Choices",
        }
        return [(ft.value, display_names.get(ft, ft.value.title())) for ft in cls]


class MandatoryFieldUuid(enum.Enum):
    """Enumeration of mandatory field UUIDs that are always present in experiments."""

    # Fixed UUIDs for mandatory fields to ensure consistency across all experiments
    MEASUREMENT_DATE = str(uuid.UUID(int=1))
    SUBMITTER_EMAIL = str(uuid.UUID(int=2))

    @classmethod
    def get_all_uuids(cls) -> list[str]:
        """Return all mandatory field UUIDs as a list."""
        return [field.value for field in cls]

    @classmethod
    def is_mandatory(cls, field_uuid: str) -> bool:
        """Check if a UUID corresponds to a mandatory field."""
        return field_uuid in cls.get_all_uuids()

    @classmethod
    def get_mandatory_fields(cls) -> dict[str, dict[str, Any]]:
        """Get all mandatory fields with their definitions."""
        return {
            cls.MEASUREMENT_DATE.value: {
                "name": "Measurement Date",
                "type": FieldType.DATE.value,
                "required": True,
                "order": 0,
            },
            cls.SUBMITTER_EMAIL.value: {
                "name": "Submitter Email",
                "type": FieldType.TEXT.value,
                "required": True,
                "order": 1,
            },
        }


class ExperimentFieldDefinition(PydanticBaseModel):
    """Pydantic model for a single field definition in experiment_fields."""

    name: Annotated[str, Field(min_length=1, description="Field display name")]
    type: Annotated[FieldType, Field(description="Field type")]
    required: Annotated[
        bool, Field(default=False, description="Whether field is required")
    ]
    order: Annotated[int, Field(ge=0, description="Display order of the field")]
    options: Annotated[
        list[str] | None,
        Field(default=None, description="Options for SELECT type fields"),
    ] = None

    @field_validator("name", mode="before")
    @classmethod
    def titlecase_name(cls, v: str) -> str:
        """Convert name to titlecase."""
        if isinstance(v, str):
            return v.title()
        return v

    @model_validator(mode="after")
    def validate_field(self) -> ExperimentFieldDefinition:
        """Validate field properties."""
        # Validate options for SELECT type fields
        if self.options is not None and self.type != FieldType.SELECT:
            raise ValueError(
                f"Field 'options' is only valid for '{FieldType.SELECT.value}' type "
                "fields"
            )
        if self.type == FieldType.SELECT and not self.options:
            raise ValueError(
                f"Field type '{FieldType.SELECT.value}' requires 'options' to be "
                "provided"
            )

        return self


def _validate_and_parse_fields_dict(
    v: dict[str, Any],
) -> dict[str, ExperimentFieldDefinition]:
    """
    Validate UUID format and parse field data, converting string types to FieldType
    enum. Returns the VALIDATED data (with transformations like titlecase applied).

    Keeps UUID as strings to preserve exact representation.
    Handles temp_ prefixed keys separately (not valid UUIDs).
    """
    if not isinstance(v, dict):
        raise TypeError("Experiment fields must be a dictionary")

    processed_data: dict[str, ExperimentFieldDefinition] = {}

    for field_key, field_data in v.items():
        # Handle temp UUIDs - they'll be processed in save()
        if field_key.startswith("temp_"):
            processed_data[field_key] = ExperimentFieldDefinition(**field_data)
            continue

        # Validate UUID format (but keep as string)
        try:
            UUID(field_key)  # Validates format
        except (ValueError, AttributeError) as e:
            raise ValueError(
                f"Invalid UUID '{field_key}'. Field keys must be valid UUIDs or "
                "'temp_' prefixed."
            ) from e

        # Convert type string to FieldType enum if needed
        if isinstance(field_data, dict) and "type" in field_data:
            _field_data = field_data.copy()
            if isinstance(_field_data["type"], str):
                try:
                    _field_data["type"] = FieldType(_field_data["type"])
                except ValueError as e:
                    valid_types = FieldType.get_all_types()
                    raise ValueError(
                        f"Invalid field type '{_field_data['type']}'. "
                        f"Valid types: {', '.join(valid_types)}"
                    ) from e
        else:
            _field_data = field_data

        # Keep UUID as string to preserve exact representation
        processed_data[field_key] = ExperimentFieldDefinition.model_validate(
            _field_data
        )

    return processed_data


class ExperimentFieldsDict(PydanticRootModel[dict[str, ExperimentFieldDefinition]]):
    """
    Pydantic RootModel for the experiment_fields dictionary structure.

    Uses string keys (validated as UUID format) to preserve exact representation.
    RootModel allows us to work directly with the dict without a 'root' wrapper.
    Access the dict via .root property, or use model_dump() for serialization.
    """

    root: Annotated[
        dict[str, ExperimentFieldDefinition],
        BeforeValidator(_validate_and_parse_fields_dict),
    ] = Field(default_factory=dict)


class Experiment(models.Model):
    """
    A logical experiment/project (e.g., "Global Air Quality Campaign 2025").
    Does NOT imply a single location; sensors/sites/measurements are related objects.
    """

    records: models.QuerySet[ExperimentRecord]
    user_permissions: models.QuerySet[ExperimentUserPermission]

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    code = models.CharField(
        max_length=64,
        blank=True,
        help_text="Short project code, e.g. AQ-2025-GL",
    )

    name = models.CharField(max_length=255, help_text="Experiment name")

    description = models.TextField(blank=True)

    experiment_fields = models.JSONField(
        default=dict,
        blank=True,
        help_text="Field definitions for data collection at each station. "
        "Structure: {field_uuid: {name, type, required, order, options}}. "
        "Mandatory fields are identified by their UUID, not a 'mandatory' property.",
    )

    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created or submitted the entry.",
    )

    is_active = models.BooleanField(default=True)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    gis_token = models.CharField(
        "GIS Token",
        max_length=40,
        unique=True,
        blank=False,
        null=False,
        default=generate_random_token,
    )

    class Meta:
        ordering = ["-modified_date"]
        constraints = [
            # If end_date is provided, start_date must also be provided
            CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(start_date__isnull=False),
                name="end_date_requires_start_date",
            ),
            # If both dates are provided, start_date <= end_date
            CheckConstraint(
                condition=Q(start_date__isnull=True)
                | Q(end_date__isnull=True)
                | Q(start_date__lte=models.F("end_date")),
                name="start_date_lte_end_date",
            ),
        ]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active"]),
            # models.Index(fields=["gis_token"]), # Unique field already indexed
        ]

    def __str__(self) -> str:
        return self.name

    def save(
        self,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Override save to enforce field immutability and process temporary UUIDs."""
        # Ensure experiment_fields is never None (convert to empty dict)
        # JSONField doesn't allow NULL, so we normalize None to {}
        if self.experiment_fields is None:
            self.experiment_fields = {}
        # Process temporary UUIDs before validation
        self._process_temporary_uuids()

        # Run full_clean to trigger validation
        # Skip validation if explicitly requested (for migrations, etc.)
        if not kwargs.pop("skip_validation", False):
            self.full_clean()

        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
            **kwargs,
        )

    def refresh_gis_token(self) -> None:
        self.gis_token = generate_random_token()
        self.save()

    @property
    def collaborator_count(self) -> int:
        return ExperimentUserPermission.objects.filter(
            experiment=self, is_active=True
        ).count()

    @staticmethod
    def generate_field_uuid() -> str:
        """Generate a unique UUID for a field."""
        return str(uuid.uuid4())

    @staticmethod
    def _hash_field_data(field_data: dict[str, Any]) -> str:
        """
        Create a deterministic hash of field data.

        Uses sorted JSON serialization for deterministic, order-independent hashing.
        This approach is simple, works across Python/JavaScript, and doesn't depend
        on dict insertion order or string representation format.

        Excludes the 'hash' field itself from the calculation.
        """
        # Create a copy without the hash field
        data_to_hash = {k: v for k, v in field_data.items() if k != "hash"}

        # Serialize with sorted keys and compact separators for deterministic output
        # sort_keys=True ensures order independence
        # separators=(',', ':') matches JavaScript's JSON.stringify() compact format
        serialized = json.dumps(data_to_hash, sort_keys=True, separators=(",", ":"))

        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _parse_fields_dict(
        self, fields: Any, exclude_temp: bool = True
    ) -> ExperimentFieldsDict:
        """
        Parse and validate fields dict using Pydantic RootModel.

        Args:
            fields: The fields dictionary to parse (will be validated)
            exclude_temp: If True, exclude temp UUIDs from validation

        Returns:
            ExperimentFieldsDict instance (with UUID type keys)

        Raises:
            ValidationError: If fields structure is invalid (not a dict or
                invalid structure)
        """
        if fields is None:
            fields = {}

        if not isinstance(fields, dict):
            raise ValidationError(
                {
                    "experiment_fields": [
                        "Experiment fields must be a dictionary with UUID keys."
                    ]
                }
            )

        # Skip validation for temp UUIDs - they'll be processed in save()
        # Note: Pydantic validator will handle separating temp keys
        fields_to_validate = (
            {k: v for k, v in fields.items() if not k.startswith("temp_")}
            if exclude_temp
            else fields
        )

        try:
            return ExperimentFieldsDict.model_validate(fields_to_validate)
        except PydanticValidationError as e:
            raise pydantic_to_django_validation_error(e) from e
        except ValueError as e:
            raise ValidationError({"experiment_fields": [str(e)]}) from e

    def _validate_experiment_fields_structure(self) -> None:
        """
        Validate that experiment_fields follows the correct structure using Pydantic.

        Note: Titlecase transformation is applied by Pydantic during API requests.
        For direct model usage (tests, factory), we trust the data is correct.

        Mandatory fields are identified by their UUID (from MandatoryFieldUuid enum),
        not by a 'mandatory' property in the field data.
        """
        # Handle None - should have been converted to {} in save()
        if self.experiment_fields is None:
            return

        # Just validate structure, don't transform
        # Transformation happens in serializer for API requests
        self._parse_fields_dict(self.experiment_fields, exclude_temp=True)

    def _validate_field_name_uniqueness(self) -> None:
        """
        Validate that field names are unique within the experiment (case-insensitive).
        Works with string keys from Django JSONField.
        Each unique name can only appear once across all field UUIDs.
        """
        if not self.experiment_fields:
            return

        # Collect all field names (normalized to lowercase for comparison)
        names_seen: dict[str, str] = {}  # lowercase_name -> field_uuid_str

        for field_key, field_data in self.experiment_fields.items():
            # Skip temp UUIDs - they'll be processed in save()
            if field_key.startswith("temp_"):
                continue

            field_name = field_data.get("name", "")
            if not field_name:
                continue

            # Normalize name for comparison (case-insensitive)
            normalized_name = field_name.lower()

            if normalized_name in names_seen:
                # Found duplicate name - check if it's a different field
                other_uuid_key = names_seen[normalized_name]
                # Normalize both UUIDs for comparison (case-insensitive UUID comparison)
                if other_uuid_key.lower() != field_key.lower():
                    # Different UUID with same name = duplicate
                    logger.debug(
                        f"Duplicate name detected: '{field_name}' appears in both "
                        f"{other_uuid_key} and {field_key}"
                    )
                    raise ValidationError(
                        {
                            "experiment_fields": [
                                f"Field name '{field_name}' is not unique. "
                                f"Another field with the same name already exists. "
                                "Field names must be unique within an experiment."
                            ]
                        }
                    )
                # Same UUID with same name = OK (e.g., after transformation)
            else:
                names_seen[normalized_name] = field_key

    def _validate_experiment_fields_immutability(self) -> None:
        """
        Validate that existing experiment fields follow immutability rules.
        - UUIDs cannot be changed or removed
        - Field type, required, and options cannot be modified
        - Field name and order CAN be modified
        Uses Pydantic models for comparison.
        """
        # Use _state.adding because pk is set before save for UUIDField
        if self._state.adding:
            # New instance, no validation needed
            return

        try:
            # Get the existing instance from database
            old_instance = Experiment.objects.get(pk=self.pk)
            old_fields = self._parse_fields_dict(
                old_instance.experiment_fields, exclude_temp=False
            )
            new_fields = self._parse_fields_dict(
                self.experiment_fields, exclude_temp=False
            )

            # Check removals - UUIDs cannot be removed
            # Keys are strings now (not UUID objects)
            old_uuids = set(old_fields.root.keys())
            new_uuids = set(new_fields.root.keys())

            removed_uuid_strs = old_uuids - new_uuids
            if removed_uuid_strs:
                # Find names for removed UUIDs
                field_names = [
                    old_fields.root[uuid_str].name for uuid_str in removed_uuid_strs
                ]
                raise ValidationError(
                    {
                        "experiment_fields": [
                            f"Cannot remove existing fields: {', '.join(field_names)}. "
                            "Fields are immutable once created to maintain data "
                            "integrity."
                        ]
                    }
                )

            # Check modifications - only type, required, and options are immutable
            # name and order CAN be changed
            modified_fields = []
            for field_uuid in old_fields.root:
                if field_uuid in new_fields.root:
                    old_field = old_fields.root[field_uuid]
                    new_field = new_fields.root[field_uuid]

                    # Check if immutable properties changed
                    if (
                        old_field.type != new_field.type
                        or old_field.required != new_field.required
                        or old_field.options != new_field.options
                    ):
                        modified_fields.append(old_field.name)

            if modified_fields:
                raise ValidationError(
                    {
                        "experiment_fields": [
                            "Cannot modify type, required status, or options of "
                            f"existing fields: {', '.join(modified_fields)}. "
                            "Only name and order can be changed."
                        ]
                    }
                )

        except Experiment.DoesNotExist:
            # This shouldn't happen, but if it does, allow the save
            logger.warning(f"Experiment {self.pk} not found during field validation")
            return

    def _process_temporary_uuids(self) -> None:
        """
        Process temporary UUIDs from admin widget and convert them to proper UUIDs.

        Temporary UUIDs start with 'temp_' and need to be replaced with proper UUIDs.
        """
        if not self.experiment_fields:
            return

        # Get existing UUIDs (including mandatory fields)
        existing_uuids = set(self.experiment_fields.keys())

        # Also include mandatory field UUIDs that should always be present
        mandatory_uuids = set(MandatoryFieldUuid.get_all_uuids())
        existing_uuids.update(mandatory_uuids)

        # Process temp UUIDs
        temp_fields = {}
        processed_fields = {}

        for field_uuid, field_data in self.experiment_fields.items():
            if field_uuid.startswith("temp_"):
                # This is a temporary UUID - process it
                temp_fields[field_uuid] = field_data
            else:
                # Keep existing fields as-is
                processed_fields[field_uuid] = field_data

        # Generate proper UUIDs for temp fields
        for field_data in temp_fields.values():
            field_name = field_data.get("name", "")
            if not field_name:
                continue  # Skip fields without names

            # Generate proper UUID
            proper_uuid = self.generate_field_uuid()
            existing_uuids.add(proper_uuid)

            # Remove hash if present (no longer needed)
            field_data_copy = field_data.copy()
            field_data_copy.pop("hash", None)

            processed_fields[proper_uuid] = field_data_copy

        # Ensure mandatory fields are present
        mandatory_fields = MandatoryFieldUuid.get_mandatory_fields()
        for field_uuid, mandatory_field_data in mandatory_fields.items():
            if field_uuid not in processed_fields:
                # Create a copy to avoid modifying the original
                processed_fields[field_uuid] = mandatory_field_data.copy()

        self.experiment_fields = processed_fields

    def _apply_titlecase_to_field_names(self) -> None:
        """
        Apply titlecase transformation to all field names.
        This ensures consistency whether fields are created via API (serializer)
        or directly via model.
        """
        if not self.experiment_fields:
            return

        # Only process if experiment_fields is a dict
        # If it's not, let the validation step catch the error
        if not isinstance(self.experiment_fields, dict):
            return

        for field_data in self.experiment_fields.values():
            if "name" in field_data and isinstance(field_data["name"], str):
                field_data["name"] = field_data["name"].title()

    def clean(self) -> None:
        """Validate the model before saving."""
        super().clean()
        # Apply titlecase to field names
        self._apply_titlecase_to_field_names()
        # Validate structure
        self._validate_experiment_fields_structure()
        # Always validate name uniqueness (for both creates and updates)
        self._validate_field_name_uniqueness()
        # Validate immutability rules (for updates only)
        self._validate_experiment_fields_immutability()

    def get_mandatory_fields_with_uuids(self) -> dict[str, dict[str, Any]]:
        """
        Get the mandatory fields (Measurement Date, Submitter Email) with their UUIDs.
        Useful for initializing new experiments.
        """
        return MandatoryFieldUuid.get_mandatory_fields()

    def is_mandatory_field(self, field_uuid: str) -> bool:
        """Check if a field UUID corresponds to a mandatory field."""
        return MandatoryFieldUuid.is_mandatory(field_uuid)

    def get_field_by_uuid(self, field_uuid: str) -> dict[str, Any] | None:
        """Get field definition by UUID. Returns None if not found."""
        return self.experiment_fields.get(field_uuid)  # type: ignore[no-any-return]

    def get_field_by_name(self, name: str) -> tuple[str, dict[str, Any]] | None:
        """
        Get field UUID and definition by name (case-insensitive).
        Returns (uuid, field_dict) tuple or None if not found.
        """
        normalized_name = name.lower()
        for field_uuid, field_data in self.experiment_fields.items():
            if field_data.get("name", "").lower() == normalized_name:
                return field_uuid, field_data
        return None

    def get_sorted_fields(self) -> list[tuple[str, dict[str, Any]]]:
        """Get fields as list of (uuid, field_dict) tuples, sorted by order."""
        return sorted(
            self.experiment_fields.items(), key=lambda x: x[1].get("order", 999)
        )


class ExperimentRecord(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    experiment = models.ForeignKey(
        Experiment,
        related_name="records",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    station = models.ForeignKey(
        Station,
        related_name="records",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Data record for an experiment. Structure: {field_uuid: value}. ",
    )

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        indexes = [
            models.Index(fields=["experiment"]),
            models.Index(fields=["experiment", "station"]),
        ]

    def __str__(self) -> str:
        return str(self.id)


class ExperimentUserPermission(models.Model):
    user = models.ForeignKey(
        User,
        related_name="experiment_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    experiment = models.ForeignKey(
        Experiment,
        related_name="user_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    level = models.IntegerField(
        choices=PermissionLevel.choices_no_webviewer,
        default=PermissionLevel.READ_ONLY,
        null=False,
        blank=False,
    )

    is_active = models.BooleanField(default=True)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    deactivated_by = models.ForeignKey(
        User,
        on_delete=models.RESTRICT,
        blank=True,
        null=True,
        default=None,
    )

    class Meta:
        verbose_name = "Experiment - User Permission"
        verbose_name_plural = "Experiment - User Permissions"
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["experiment", "is_active"]),
            models.Index(fields=["user", "experiment", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "experiment"],
                name="%(app_label)s_%(class)s_user_experiment_perm_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} => {self.experiment} [{self.level}]"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def deactivate(self, deactivated_by: User) -> None:
        self.is_active = False
        self.deactivated_by = deactivated_by
        self.save()

    def reactivate(self, level: PermissionLevel) -> None:
        self.is_active = True
        self.deactivated_by = None
        self.level = level
        self.save()

    @property
    def level_label(self) -> StrOrPromise:
        return PermissionLevel.from_value(self.level).label
