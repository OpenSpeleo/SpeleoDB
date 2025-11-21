"""Tests for Experiment model, focusing on field immutability."""

from __future__ import annotations

import re

import pytest
from django.core.exceptions import ValidationError

from speleodb.gis.models import Experiment
from speleodb.gis.models.experiment import ExperimentFieldDefinition
from speleodb.gis.models.experiment import ExperimentFieldsDict
from speleodb.gis.models.experiment import FieldType
from speleodb.gis.models.experiment import MandatoryFieldUuid


@pytest.mark.django_db
class TestExperimentModel:
    """Test cases for Experiment model."""

    def test_create_experiment_with_fields(self) -> None:
        """Test creating an experiment with custom fields."""
        ph_uuid = Experiment.generate_field_uuid()
        temp_uuid = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            code="EXP-001",
            description="Test description",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                ph_uuid: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
                temp_uuid: {
                    "name": "Temperature",
                    "type": FieldType.NUMBER.value,
                    "required": True,
                    "order": 3,
                },
            },
        )

        assert experiment.id is not None
        assert experiment.name == "Test Experiment"
        assert isinstance(experiment.experiment_fields, dict)
        assert "00000000-0000-0000-0000-000000000001" in experiment.experiment_fields
        assert "00000000-0000-0000-0000-000000000002" in experiment.experiment_fields
        assert ph_uuid in experiment.experiment_fields
        assert temp_uuid in experiment.experiment_fields
        assert len(experiment.experiment_fields) == 4  # noqa: PLR2004

    def test_cannot_remove_existing_field(self) -> None:
        """Test that existing fields cannot be removed."""
        ph_uuid = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                ph_uuid: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
            },
        )

        # Try to remove ph_level field
        experiment.experiment_fields.pop(ph_uuid)

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        assert "Cannot remove existing fields" in str(exc_info.value.message_dict)

    def test_cannot_remove_mandatory_field(self) -> None:
        """Test that mandatory fields cannot be removed."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields=MandatoryFieldUuid.get_mandatory_fields(),
        )

        # Try to remove mandatory field
        experiment.experiment_fields.pop("00000000-0000-0000-0000-000000000001")

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        assert "Cannot remove existing fields" in str(exc_info.value.message_dict)
        assert "Measurement Date" in str(exc_info.value.message_dict)

    def test_can_modify_existing_field_name(self) -> None:
        """Test that existing field names CAN be modified."""
        ph_uuid = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                ph_uuid: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
            },
        )

        # Try to modify field name - this should be ALLOWED
        experiment.experiment_fields[ph_uuid]["name"] = "Modified Ph Level"

        # Should not raise validation error
        experiment.full_clean()
        experiment.save()

        # Verify the name was changed
        experiment.refresh_from_db()
        assert experiment.experiment_fields[ph_uuid]["name"] == "Modified Ph Level"

    def test_cannot_modify_existing_field_type(self) -> None:
        """Test that existing field types cannot be modified."""
        ph_uuid = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                ph_uuid: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
            },
        )

        # Try to modify field type
        experiment.experiment_fields[ph_uuid]["type"] = FieldType.TEXT.value

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        assert "Cannot modify" in str(exc_info.value.message_dict)

    def test_cannot_modify_existing_field_required(self) -> None:
        """Test that existing field required status cannot be modified."""
        ph_uuid = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                ph_uuid: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
            },
        )

        # Try to modify required status
        experiment.experiment_fields[ph_uuid]["required"] = True

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        assert "Cannot modify" in str(exc_info.value.message_dict)

    def test_cannot_modify_existing_select_field_options(self) -> None:
        """Test that existing select field options cannot be modified."""
        quality_uuid = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                quality_uuid: {
                    "name": "Water Quality",
                    "type": FieldType.SELECT.value,
                    "required": False,
                    "order": 2,
                    "options": ["Good", "Fair", "Poor"],
                },
            },
        )

        # Try to modify options
        experiment.experiment_fields[quality_uuid]["options"] = [
            "Excellent",
            "Good",
        ]

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        assert "Cannot modify" in str(exc_info.value.message_dict)

    def test_can_add_new_field(self) -> None:
        """Test that new fields can be added to existing experiment."""
        ph_uuid = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                ph_uuid: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
            },
        )

        original_field_count = len(experiment.experiment_fields)

        # Add new field
        temp_uuid = Experiment.generate_field_uuid()
        experiment.experiment_fields[temp_uuid] = {
            "name": "Temperature",
            "type": FieldType.NUMBER.value,
            "required": True,
            "order": 3,
        }

        # Should not raise validation error
        experiment.full_clean()
        experiment.save()

        # Verify new field was added
        experiment.refresh_from_db()
        assert len(experiment.experiment_fields) == original_field_count + 1
        assert temp_uuid in experiment.experiment_fields
        assert experiment.experiment_fields[temp_uuid]["name"] == "Temperature"

    def test_can_add_multiple_new_fields(self) -> None:
        """Test that multiple new fields can be added."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields=MandatoryFieldUuid.get_mandatory_fields(),
        )

        # Add multiple new fields
        ph_uuid = Experiment.generate_field_uuid()
        temp_uuid = Experiment.generate_field_uuid()
        notes_uuid = Experiment.generate_field_uuid()

        experiment.experiment_fields[ph_uuid] = {
            "name": "Ph Level",
            "type": FieldType.NUMBER.value,
            "required": False,
            "order": 2,
        }
        experiment.experiment_fields[temp_uuid] = {
            "name": "Temperature",
            "type": FieldType.NUMBER.value,
            "required": True,
            "order": 3,
        }
        experiment.experiment_fields[notes_uuid] = {
            "name": "Notes",
            "type": FieldType.TEXT.value,
            "required": False,
            "order": 4,
        }

        # Should not raise validation error
        experiment.full_clean()
        experiment.save()

        # Verify all fields were added
        experiment.refresh_from_db()
        assert len(experiment.experiment_fields) == 5  # noqa: PLR2004
        assert ph_uuid in experiment.experiment_fields
        assert temp_uuid in experiment.experiment_fields
        assert notes_uuid in experiment.experiment_fields

    def test_mandatory_fields_always_present(self) -> None:
        """Test that mandatory fields are always present."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields=MandatoryFieldUuid.get_mandatory_fields(),
        )

        # Verify mandatory fields exist
        assert "00000000-0000-0000-0000-000000000001" in experiment.experiment_fields
        assert "00000000-0000-0000-0000-000000000002" in experiment.experiment_fields

        # Verify their data
        assert (
            experiment.experiment_fields["00000000-0000-0000-0000-000000000001"]["name"]
            == "Measurement Date"
        )
        assert (
            experiment.experiment_fields["00000000-0000-0000-0000-000000000002"]["name"]
            == "Submitter Email"
        )

    def test_immutability_check_skipped_for_new_instance(self) -> None:
        """Test that immutability check is skipped for new instances."""
        ph_uuid = Experiment.generate_field_uuid()

        experiment = Experiment(
            name="New Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                ph_uuid: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
            },
        )

        # Should not raise validation error (no pk yet)
        experiment.full_clean()
        experiment.save()

        assert experiment.id is not None

    def test_remove_and_modify_attempts_raise_validation_error(self) -> None:
        """Test that attempting both removal and immutable modification raises error."""
        ph_uuid = Experiment.generate_field_uuid()
        temp_uuid = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                ph_uuid: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
                temp_uuid: {
                    "name": "Temperature",
                    "type": FieldType.NUMBER.value,
                    "required": True,
                    "order": 3,
                },
            },
        )

        # Try to remove one field and modify an immutable property of another
        experiment.experiment_fields.pop(ph_uuid)
        experiment.experiment_fields[temp_uuid]["type"] = (
            FieldType.TEXT.value
        )  # Modify immutable property

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        # Should mention removal (checked first)
        error_message = str(exc_info.value.message_dict)
        assert "Cannot remove" in error_message

    def test_field_structure_validation(self) -> None:
        """Test that field structure validation works correctly."""
        experiment = Experiment(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                "invalid-uuid-format": {  # Invalid UUID format
                    "name": "Invalid Field",
                    "type": FieldType.TEXT.value,
                    "required": False,
                    "order": 0,
                },
            },
        )

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict

    def test_field_missing_required_keys(self) -> None:
        """Test that fields missing required keys raise validation error."""
        test_uuid = Experiment.generate_field_uuid()

        experiment = Experiment(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                test_uuid: {
                    "name": "Test Field",
                    # Missing "type", "required", and "order"
                },
            },
        )

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        # Pydantic error message format: "type: Field required"
        assert "Field required" in str(exc_info.value.message_dict)

    def test_invalid_field_type(self) -> None:
        """Test that invalid field types raise validation error."""
        test_uuid = Experiment.generate_field_uuid()

        experiment = Experiment(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                test_uuid: {
                    "name": "Test Field",
                    "type": "invalid_type",
                    "required": False,
                    "order": 2,
                },
            },
        )

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        # Pydantic error message format includes "Invalid field type"
        assert "Invalid field type" in str(exc_info.value.message_dict)

    def test_options_only_for_select_type(self) -> None:
        """Test that options are only valid for select type fields."""
        test_uuid = Experiment.generate_field_uuid()

        experiment = Experiment(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                test_uuid: {
                    "name": "Test Field",
                    "type": FieldType.TEXT.value,
                    "required": False,
                    "order": 2,
                    "options": ["Option 1", "Option 2"],  # Invalid: not select type
                },
            },
        )

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        # Pydantic error message format: "Field 'options' is only valid for 'select'
        # type fields"
        assert "options" in str(exc_info.value.message_dict).lower()
        assert "select" in str(exc_info.value.message_dict).lower()

    def test_uuid_generation(self) -> None:
        """Test that UUID generation works correctly."""
        uuid1 = Experiment.generate_field_uuid()
        uuid2 = Experiment.generate_field_uuid()

        # UUIDs should be valid UUID format

        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        assert re.match(uuid_pattern, uuid1, re.IGNORECASE)
        assert re.match(uuid_pattern, uuid2, re.IGNORECASE)

        # UUIDs should be unique
        assert uuid1 != uuid2

    def test_experiment_string_representation(self) -> None:
        """Test the string representation of Experiment."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
        )

        assert experiment.name == str(experiment)

    def test_experiment_ordering(self) -> None:
        """Test that experiments are ordered by creation date descending."""
        Experiment.objects.create(
            name="First Experiment",
            created_by="test@example.com",
        )
        Experiment.objects.create(
            name="Second Experiment",
            created_by="test@example.com",
        )
        Experiment.objects.create(
            name="Third Experiment",
            created_by="test@example.com",
        )

        experiments = list(Experiment.objects.all())

        # Should be ordered by creation_date descending (newest first)
        assert experiments[0].name == "Third Experiment"
        assert experiments[1].name == "Second Experiment"
        assert experiments[2].name == "First Experiment"

    def test_timestamps_auto_update(self) -> None:
        """Test that timestamps are automatically managed."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
        )

        original_created = experiment.creation_date
        original_modified = experiment.modified_date

        # Update the experiment
        experiment.description = "Updated description"
        experiment.save()

        # creation_date should not change
        assert experiment.creation_date == original_created

        # modified_date should be updated
        assert experiment.modified_date > original_modified

    def test_save_without_modifying_fields(self) -> None:
        """Test that saving without modifying fields works correctly."""
        ph_uuid = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                ph_uuid: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
            },
        )

        original_fields = experiment.experiment_fields.copy()

        # Modify non-field attribute
        experiment.description = "New description"
        experiment.save()

        # Fields should remain unchanged
        experiment.refresh_from_db()
        assert experiment.experiment_fields == original_fields

    def test_rootmodel_direct_validation(self) -> None:
        """Test that RootModel validates dict directly without wrapper."""
        test_uuid = Experiment.generate_field_uuid()

        fields_dict = {
            test_uuid: {
                "name": "Test Field",
                "type": FieldType.TEXT.value,
                "required": False,
                "order": 0,
            }
        }

        # Should validate directly without {"root": ...} wrapper
        fields_model = ExperimentFieldsDict.model_validate(fields_dict)
        # Keys are strings (preserves exact UUID representation)
        assert test_uuid in fields_model.root
        assert fields_model.root[test_uuid].name == "Test Field"

    def test_validation_with_temp_uuids(self) -> None:
        """Test that validation excludes temp UUIDs (they're processed in save())."""
        test_uuid = Experiment.generate_field_uuid()

        experiment = Experiment(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                test_uuid: {
                    "name": "Test Field",
                    "type": FieldType.TEXT.value,
                    "required": False,
                    "order": 2,
                },
                "temp_123": {
                    "name": "Water Quality",
                    "type": FieldType.TEXT.value,
                    "required": False,
                    "order": 3,
                },
            },
        )

        # Should validate successfully (temp UUIDs are excluded from validation)
        experiment.full_clean()
        experiment.save()

        # After save, temp UUIDs should be processed into proper UUIDs
        experiment.refresh_from_db()
        assert test_uuid in experiment.experiment_fields
        # temp_123 should have been converted to a proper UUID
        # Find the field by name
        water_quality_uuid = None
        for field_uuid, field_data in experiment.experiment_fields.items():
            if field_data.get("name") == "Water Quality":
                water_quality_uuid = field_uuid
                break
        assert water_quality_uuid is not None
        assert "temp_123" not in experiment.experiment_fields

    def test_validation_with_invalid_field_type(self) -> None:
        """Test that validation raises error for invalid field types."""
        experiment = Experiment(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields="not a dict",
        )

        # Should raise ValidationError for non-dict
        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict

    def test_validation_with_none_fields(self) -> None:
        """Test that validation handles None fields gracefully."""
        experiment = Experiment(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields=None,
        )

        # Should handle None and validate successfully (treated as empty dict)
        experiment.full_clean()
        experiment.save()

        # Fields should be empty dict after save
        experiment.refresh_from_db()
        assert experiment.experiment_fields == {}

    def test_model_dump_serialization(self) -> None:
        """Test that model_dump() works correctly for serialization."""

        field_def = ExperimentFieldDefinition(
            name="Test Field",
            type=FieldType.TEXT,
            required=True,
            order=0,
        )

        # Should serialize correctly
        dumped = field_def.model_dump(mode="json", exclude_none=True)
        assert dumped["name"] == "Test Field"
        assert dumped["type"] == FieldType.TEXT.value
        assert dumped["required"] is True
        assert dumped["order"] == 0
        assert "options" not in dumped  # Should be excluded when None

    def test_model_dump_with_options(self) -> None:
        """Test that model_dump() includes options when present."""

        field_def = ExperimentFieldDefinition(
            name="Quality",
            type=FieldType.SELECT,
            required=False,
            order=0,
            options=["Good", "Fair", "Poor"],
        )

        dumped = field_def.model_dump(mode="json", exclude_none=True)
        assert dumped["options"] == ["Good", "Fair", "Poor"]

    def test_field_name_uniqueness_case_insensitive(self) -> None:
        """Test that field names must be unique (case-insensitive)."""
        uuid1 = Experiment.generate_field_uuid()
        uuid2 = Experiment.generate_field_uuid()

        experiment = Experiment(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                uuid1: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
                uuid2: {
                    "name": "pH Level",  # Same name, different case
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 3,
                },
            },
        )

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        assert "not unique" in str(exc_info.value.message_dict).lower()

    def test_field_name_titlecase_enforcement(self) -> None:
        """Test that field names are automatically converted to titlecase."""
        uuid1 = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                uuid1: {
                    "name": "ph level",  # lowercase
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
            },
        )

        # Verify name was converted to titlecase
        experiment.refresh_from_db()
        assert experiment.experiment_fields[uuid1]["name"] == "Ph Level"

    def test_order_field_present(self) -> None:
        """Test that order field is required and present."""
        uuid1 = Experiment.generate_field_uuid()

        # Create experiment with order field
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                uuid1: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 5,
                },
            },
        )

        # Verify order field is present and correct
        experiment.refresh_from_db()
        assert experiment.experiment_fields[uuid1]["order"] == 5  # noqa: PLR2004

    def test_can_modify_order_field(self) -> None:
        """Test that order field can be modified."""
        uuid1 = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                uuid1: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
            },
        )

        # Modify order
        experiment.experiment_fields[uuid1]["order"] = 10

        # Should not raise validation error
        experiment.full_clean()
        experiment.save()

        # Verify order was changed
        experiment.refresh_from_db()
        assert experiment.experiment_fields[uuid1]["order"] == 10  # noqa: PLR2004

    def test_order_field_negative_value(self) -> None:
        """Test that negative order values are rejected."""
        uuid1 = Experiment.generate_field_uuid()

        experiment = Experiment(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                uuid1: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": -1,  # Invalid: negative
                },
            },
        )

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict

    def test_order_field_duplicate_values_allowed(self) -> None:
        """Test that duplicate order values are allowed (UI will handle)."""
        uuid1 = Experiment.generate_field_uuid()
        uuid2 = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                uuid1: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 5,
                },
                uuid2: {
                    "name": "Temperature",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 5,  # Same order - should be allowed
                },
            },
        )

        # Should not raise validation error
        experiment.full_clean()
        experiment.save()

        experiment.refresh_from_db()
        assert experiment.experiment_fields[uuid1]["order"] == 5  # noqa: PLR2004
        assert experiment.experiment_fields[uuid2]["order"] == 5  # noqa: PLR2004

    def test_name_editing_preserves_uuid(self) -> None:
        """Test that editing a field name doesn't change its UUID."""
        uuid1 = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                uuid1: {
                    "name": "Original Name",
                    "type": FieldType.TEXT.value,
                    "required": False,
                    "order": 2,
                },
            },
        )

        # Edit the name
        experiment.experiment_fields[uuid1]["name"] = "Edited Name"
        experiment.full_clean()
        experiment.save()

        # Verify UUID is the same but name changed
        experiment.refresh_from_db()
        assert uuid1 in experiment.experiment_fields
        assert experiment.experiment_fields[uuid1]["name"] == "Edited Name"

    def test_name_uniqueness_prevents_duplicate(self) -> None:
        """Test that duplicate names are prevented."""
        uuid1 = Experiment.generate_field_uuid()
        uuid2 = Experiment.generate_field_uuid()

        experiment = Experiment(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                uuid1: {
                    "name": "Water Quality",
                    "type": FieldType.TEXT.value,
                    "required": False,
                    "order": 2,
                },
                uuid2: {
                    "name": "water quality",  # Different case but same name
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 3,
                },
            },
        )

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        assert "not unique" in str(exc_info.value.message_dict).lower()

    def test_name_edit_to_duplicate_prevents_save(self) -> None:
        """Test that editing a name to match another field is prevented."""
        uuid1 = Experiment.generate_field_uuid()
        uuid2 = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                uuid1: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
                uuid2: {
                    "name": "Temperature",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 3,
                },
            },
        )

        # Try to edit uuid2's name to match uuid1
        experiment.experiment_fields[uuid2]["name"] = "Ph Level"

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        assert "not unique" in str(exc_info.value.message_dict).lower()

    def test_titlecase_with_special_characters(self) -> None:
        """Test titlecase conversion with special characters."""
        uuid1 = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                uuid1: {
                    "name": "pH level (water)",  # Mixed case with parentheses
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
            },
        )

        # Verify titlecase was applied
        experiment.refresh_from_db()
        assert experiment.experiment_fields[uuid1]["name"] == "Ph Level (Water)"

    def test_edit_name_and_order_together(self) -> None:
        """Test that both name and order can be edited simultaneously."""
        uuid1 = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                uuid1: {
                    "name": "Original",
                    "type": FieldType.TEXT.value,
                    "required": False,
                    "order": 2,
                },
            },
        )

        # Edit both name and order
        experiment.experiment_fields[uuid1]["name"] = "Modified"
        experiment.experiment_fields[uuid1]["order"] = 10

        experiment.full_clean()
        experiment.save()

        # Verify both changed
        experiment.refresh_from_db()
        assert experiment.experiment_fields[uuid1]["name"] == "Modified"
        assert experiment.experiment_fields[uuid1]["order"] == 10  # noqa: PLR2004

    def test_mandatory_field_order_preserved(self) -> None:
        """Test that mandatory fields maintain their order."""
        mandatory_fields = MandatoryFieldUuid.get_mandatory_fields()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields=mandatory_fields,
        )

        experiment.refresh_from_db()
        # Measurement Date should have order 0
        assert (
            experiment.experiment_fields["00000000-0000-0000-0000-000000000001"][
                "order"
            ]
            == 0
        )
        # Submitter Email should have order 1
        assert (
            experiment.experiment_fields["00000000-0000-0000-0000-000000000002"][
                "order"
            ]
            == 1
        )

    def test_pydantic_uuid_type_validation(self) -> None:
        """Test that Pydantic UUID type provides automatic validation."""
        # Valid UUID should work
        valid_uuid = Experiment.generate_field_uuid()
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                valid_uuid: {
                    "name": "Valid Field",
                    "type": FieldType.TEXT.value,
                    "required": False,
                    "order": 2,
                },
            },
        )
        assert valid_uuid in experiment.experiment_fields

        # Invalid UUID format should be rejected
        invalid_experiment = Experiment(
            name="Test",
            created_by="test@example.com",
            experiment_fields={
                "not-a-valid-uuid-format": {
                    "name": "Invalid",
                    "type": FieldType.TEXT.value,
                    "required": False,
                    "order": 0,
                },
            },
        )

        with pytest.raises(ValidationError) as exc_info:
            invalid_experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        assert "invalid uuid" in str(exc_info.value.message_dict).lower()

    def test_helper_methods(self) -> None:
        """Test the new helper methods for field access."""
        uuid1 = Experiment.generate_field_uuid()
        uuid2 = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldUuid.get_mandatory_fields(),
                uuid1: {
                    "name": "Field A",
                    "type": FieldType.TEXT.value,
                    "required": False,
                    "order": 10,
                },
                uuid2: {
                    "name": "Field B",
                    "type": FieldType.TEXT.value,
                    "required": False,
                    "order": 5,
                },
            },
        )

        # Test get_field_by_uuid
        field_a = experiment.get_field_by_uuid(uuid1)
        assert field_a is not None
        assert field_a["name"] == "Field A"

        # Test get_field_by_name (case-insensitive)
        found_uuid, found_field = experiment.get_field_by_name("field b")  # type: ignore[misc]
        assert found_uuid == uuid2
        assert found_field["name"] == "Field B"

        # Test get_sorted_fields
        sorted_fields = experiment.get_sorted_fields()
        field_names = [field["name"] for uuid, field in sorted_fields]
        # Should be sorted by order:
        # Measurement Date (0), Submitter Email (1), Field B (5), Field A (10)
        assert field_names == [
            "Measurement Date",
            "Submitter Email",
            "Field B",
            "Field A",
        ]
