# -*- coding: utf-8 -*-

from __future__ import annotations

import binascii
import enum
import hashlib
import json
import logging
import os
import re
import uuid
from typing import TYPE_CHECKING
from typing import Annotated
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CheckConstraint
from django.db.models import Q
from django.utils.text import slugify
from pydantic import BaseModel
from pydantic import BeforeValidator
from pydantic import Field
from pydantic import RootModel
from pydantic import ValidationError as PydanticValidationError
from pydantic import model_validator

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Station
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


class MandatoryFieldSlug(enum.Enum):
    """Enumeration of mandatory field slugs that are always present in experiments."""

    MEASUREMENT_DATE = "measurement_date"
    SUBMITTER_EMAIL = "submitter_email"

    @classmethod
    def get_all_slugs(cls) -> list[str]:
        """Return all mandatory field slugs as a list."""
        return [field.value for field in cls]

    @classmethod
    def is_mandatory(cls, slug: str) -> bool:
        """Check if a slug corresponds to a mandatory field."""
        return slug in cls.get_all_slugs()

    @classmethod
    def get_mandatory_fields(cls) -> dict[str, dict[str, Any]]:
        """Get all mandatory fields with their definitions."""
        return {
            cls.MEASUREMENT_DATE.value: {
                "name": "Measurement Date",
                "type": FieldType.DATE.value,
                "required": True,
            },
            cls.SUBMITTER_EMAIL.value: {
                "name": "Submitter Email",
                "type": FieldType.TEXT.value,
                "required": True,
            },
        }


def _generate_random_token() -> str:
    return binascii.hexlify(os.urandom(20)).decode()


class ExperimentFieldDefinition(BaseModel):
    """Pydantic model for a single field definition in experiment_fields."""

    name: Annotated[str, Field(min_length=1, description="Field display name")]
    type: Annotated[FieldType, Field(description="Field type")]
    required: Annotated[
        bool, Field(default=False, description="Whether field is required")
    ]
    options: Annotated[
        list[str] | None,
        Field(default=None, description="Options for SELECT type fields"),
    ] = None

    @model_validator(mode="after")
    def validate_options_for_select(self) -> ExperimentFieldDefinition:
        """Validate that options are only present for SELECT type fields."""
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
    Validate slug format and parse field data, converting string types to FieldType
    enum.
    """
    if not isinstance(v, dict):
        raise TypeError("Experiment fields must be a dictionary")

    processed_data: dict[str, ExperimentFieldDefinition] = {}
    for slug, field_data in v.items():
        # Skip temp slugs - they'll be processed in save()
        if slug.startswith("temp_"):
            processed_data[slug] = ExperimentFieldDefinition(**field_data)
            continue

        # Validate slug format
        if not re.match(r"^[a-z][a-z0-9_]*$", slug):
            raise ValueError(
                f"Invalid slug '{slug}'. Slugs must start with a letter "
                "and contain only lowercase letters, numbers, and underscores."
            )

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

        processed_data[slug] = ExperimentFieldDefinition.model_validate(_field_data)

    return processed_data


class ExperimentFieldsDict(RootModel[dict[str, ExperimentFieldDefinition]]):
    """
    Pydantic RootModel for the experiment_fields dictionary structure.

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

    rel_records: models.QuerySet[ExperimentRecord]
    rel_user_permissions: models.QuerySet[ExperimentUserPermission]

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
        "Structure: {field_slug: {name, type, required, options}}. "
        "Mandatory fields are identified by their slug, not a 'mandatory' property.",
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
        default=_generate_random_token,
    )

    class Meta:
        ordering = ["-creation_date"]
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
            models.Index(fields=["is_active"]),
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
        """Override save to enforce field immutability and process temporary slugs."""
        # Ensure experiment_fields is never None (convert to empty dict)
        # JSONField doesn't allow NULL, so we normalize None to {}
        if self.experiment_fields is None:
            self.experiment_fields = {}
        # Process temporary slugs before validation
        self._process_temporary_slugs()

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
        self.gis_token = _generate_random_token()
        self.save()

    @property
    def collaborator_count(self) -> int:
        return ExperimentUserPermission.objects.filter(
            experiment=self, is_active=True
        ).count()

    @staticmethod
    def generate_unique_slug(name: str, existing_slugs: set[str]) -> str:
        """
        Generate a unique slug from a field name.
        Handles collisions by appending a number.
        """
        base_slug = slugify(name.lower().replace(" ", "_"))
        if not base_slug:
            base_slug = "field"

        # Ensure it starts with a letter (valid Python identifier)
        if base_slug and not base_slug[0].isalpha():
            base_slug = f"field_{base_slug}"

        slug = base_slug
        counter = 1
        while slug in existing_slugs:
            slug = f"{base_slug}_{counter}"
            counter += 1

        return slug

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
            exclude_temp: If True, exclude temp slugs from validation

        Returns:
            ExperimentFieldsDict instance

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
                        "Experiment fields must be a dictionary with slug keys."
                    ]
                }
            )

        # Skip validation for temp slugs - they'll be processed in save()
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

        Mandatory fields are identified by their slug (from MandatoryFieldSlug enum),
        not by a 'mandatory' property in the field data.
        """
        self._parse_fields_dict(self.experiment_fields, exclude_temp=True)

    def _validate_experiment_fields_immutability(self) -> None:
        """
        Validate that existing experiment fields are never removed or modified.
        Only new fields can be added. Uses Pydantic models for comparison.
        """
        if not self.pk:
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

            # Check removals
            removed_slugs = set(old_fields.root.keys()) - set(new_fields.root.keys())
            if removed_slugs:
                field_names = [old_fields.root[slug].name for slug in removed_slugs]
                raise ValidationError(
                    {
                        "experiment_fields": [
                            f"Cannot remove existing fields: {', '.join(field_names)}. "
                            "Fields are immutable once created to maintain data "
                            "integrity."
                        ]
                    }
                )

            # Check modifications - Pydantic models are comparable
            modified_fields = [
                old_fields.root[slug].name
                for slug in old_fields.root
                if slug in new_fields.root
                and old_fields.root[slug] != new_fields.root[slug]
            ]
            if modified_fields:
                raise ValidationError(
                    {
                        "experiment_fields": [
                            "Cannot modify existing fields: "
                            f"{', '.join(modified_fields)}. Fields are immutable once "
                            "created. You can only add new fields."
                        ]
                    }
                )

        except Experiment.DoesNotExist:
            # This shouldn't happen, but if it does, allow the save
            logger.warning(f"Experiment {self.pk} not found during field validation")
            return

    def _process_temporary_slugs(self) -> None:
        """
        Process temporary slugs from admin widget and convert them to proper slugs.

        Temporary slugs start with 'temp_' and need to be replaced with proper
        slugs.
        """
        if not self.experiment_fields:
            return

        # Get existing slugs (including mandatory fields)
        existing_slugs = set(self.experiment_fields.keys())

        # Also include mandatory field slugs that should always be present
        mandatory_slugs = set(MandatoryFieldSlug.get_all_slugs())
        existing_slugs.update(mandatory_slugs)

        # Process temp slugs
        temp_fields = {}
        processed_fields = {}

        for slug, field_data in self.experiment_fields.items():
            if slug.startswith("temp_"):
                # This is a temporary slug - process it
                temp_fields[slug] = field_data
            else:
                # Keep existing fields as-is
                processed_fields[slug] = field_data

        # Generate proper slugs for temp fields
        for field_data in temp_fields.values():
            field_name = field_data.get("name", "")
            if not field_name:
                continue  # Skip fields without names

            # Generate proper slug
            proper_slug = self.generate_unique_slug(field_name, existing_slugs)
            existing_slugs.add(proper_slug)

            # Remove hash if present (no longer needed)
            field_data_copy = field_data.copy()
            field_data_copy.pop("hash", None)

            processed_fields[proper_slug] = field_data_copy

        # Ensure mandatory fields are present
        mandatory_fields = MandatoryFieldSlug.get_mandatory_fields()
        for slug, mandatory_field_data in mandatory_fields.items():
            if slug not in processed_fields:
                # Create a copy to avoid modifying the original
                processed_fields[slug] = mandatory_field_data.copy()

        self.experiment_fields = processed_fields

    def clean(self) -> None:
        """Validate the model before saving."""
        super().clean()
        self._validate_experiment_fields_structure()
        self._validate_experiment_fields_immutability()

    def get_mandatory_fields_with_slugs(self) -> dict[str, dict[str, Any]]:
        """
        Get the mandatory fields (Measurement Date, Submitter Email) with their slugs.
        Useful for initializing new experiments.
        """
        return MandatoryFieldSlug.get_mandatory_fields()

    def is_mandatory_field(self, slug: str) -> bool:
        """Check if a field slug corresponds to a mandatory field."""
        return MandatoryFieldSlug.is_mandatory(slug)


class ExperimentRecord(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    experiment = models.ForeignKey(
        Experiment,
        related_name="rel_records",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    station = models.ForeignKey(
        Station,
        related_name="rel_records",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Data record for an experiment. Structure: {field_slug: value}. ",
    )

    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created or submitted the entry.",
    )

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        indexes = [
            models.Index(fields=["experiment", "station"]),
        ]

    def __str__(self) -> str:
        return str(self.id)


class ExperimentUserPermission(models.Model):
    user = models.ForeignKey(
        User,
        related_name="rel_experiment_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    experiment = models.ForeignKey(
        Experiment,
        related_name="rel_user_permissions",
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
        unique_together = ("user", "experiment")
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["experiment", "is_active"]),
            models.Index(fields=["user", "experiment", "is_active"]),
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
