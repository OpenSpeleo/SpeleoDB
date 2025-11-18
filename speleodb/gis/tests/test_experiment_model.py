"""Tests for Experiment model, focusing on field immutability."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from speleodb.gis.models import Experiment
from speleodb.gis.models.experiment import ExperimentFieldDefinition
from speleodb.gis.models.experiment import ExperimentFieldsDict
from speleodb.gis.models.experiment import FieldType
from speleodb.gis.models.experiment import MandatoryFieldSlug


@pytest.mark.django_db
class TestExperimentModel:
    """Test cases for Experiment model."""

    def test_create_experiment_with_fields(self) -> None:
        """Test creating an experiment with custom fields."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            code="EXP-001",
            description="Test description",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldSlug.get_mandatory_fields(),
                "ph_level": {
                    "name": "pH Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                },
                "temperature": {
                    "name": "Temperature",
                    "type": FieldType.NUMBER.value,
                    "required": True,
                },
            },
        )

        assert experiment.id is not None
        assert experiment.name == "Test Experiment"
        assert isinstance(experiment.experiment_fields, dict)
        assert "measurement_date" in experiment.experiment_fields
        assert "submitter_email" in experiment.experiment_fields
        assert "ph_level" in experiment.experiment_fields
        assert "temperature" in experiment.experiment_fields
        assert len(experiment.experiment_fields) == 4  # noqa: PLR2004

    def test_cannot_remove_existing_field(self) -> None:
        """Test that existing fields cannot be removed."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldSlug.get_mandatory_fields(),
                "ph_level": {
                    "name": "pH Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                },
            },
        )

        # Try to remove ph_level field
        experiment.experiment_fields.pop("ph_level")

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        assert "Cannot remove existing fields" in str(exc_info.value.message_dict)

    def test_cannot_remove_mandatory_field(self) -> None:
        """Test that mandatory fields cannot be removed."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields=MandatoryFieldSlug.get_mandatory_fields(),
        )

        # Try to remove mandatory field
        experiment.experiment_fields.pop("measurement_date")

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        assert "Cannot remove existing fields" in str(exc_info.value.message_dict)
        assert "Measurement Date" in str(exc_info.value.message_dict)

    def test_cannot_modify_existing_field_name(self) -> None:
        """Test that existing field names cannot be modified."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldSlug.get_mandatory_fields(),
                "ph_level": {
                    "name": "pH Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                },
            },
        )

        # Try to modify field name
        experiment.experiment_fields["ph_level"]["name"] = "Modified pH Level"

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        assert "Cannot modify existing fields" in str(exc_info.value.message_dict)

    def test_cannot_modify_existing_field_type(self) -> None:
        """Test that existing field types cannot be modified."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldSlug.get_mandatory_fields(),
                "ph_level": {
                    "name": "pH Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                },
            },
        )

        # Try to modify field type
        experiment.experiment_fields["ph_level"]["type"] = FieldType.TEXT.value

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        assert "Cannot modify existing fields" in str(exc_info.value.message_dict)

    def test_cannot_modify_existing_field_required(self) -> None:
        """Test that existing field required status cannot be modified."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldSlug.get_mandatory_fields(),
                "ph_level": {
                    "name": "pH Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                },
            },
        )

        # Try to modify required status
        experiment.experiment_fields["ph_level"]["required"] = True

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        assert "Cannot modify existing fields" in str(exc_info.value.message_dict)

    def test_cannot_modify_existing_select_field_options(self) -> None:
        """Test that existing select field options cannot be modified."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldSlug.get_mandatory_fields(),
                "water_quality": {
                    "name": "Water Quality",
                    "type": FieldType.SELECT.value,
                    "required": False,
                    "options": ["Good", "Fair", "Poor"],
                },
            },
        )

        # Try to modify options
        experiment.experiment_fields["water_quality"]["options"] = [
            "Excellent",
            "Good",
        ]

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        assert "Cannot modify existing fields" in str(exc_info.value.message_dict)

    def test_can_add_new_field(self) -> None:
        """Test that new fields can be added to existing experiment."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldSlug.get_mandatory_fields(),
                "ph_level": {
                    "name": "pH Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                },
            },
        )

        original_field_count = len(experiment.experiment_fields)

        # Add new field
        experiment.experiment_fields["temperature"] = {
            "name": "Temperature",
            "type": FieldType.NUMBER.value,
            "required": True,
        }

        # Should not raise validation error
        experiment.full_clean()
        experiment.save()

        # Verify new field was added
        experiment.refresh_from_db()
        assert len(experiment.experiment_fields) == original_field_count + 1
        assert "temperature" in experiment.experiment_fields
        assert experiment.experiment_fields["temperature"]["name"] == "Temperature"

    def test_can_add_multiple_new_fields(self) -> None:
        """Test that multiple new fields can be added."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields=MandatoryFieldSlug.get_mandatory_fields(),
        )

        # Add multiple new fields
        experiment.experiment_fields["ph_level"] = {
            "name": "pH Level",
            "type": FieldType.NUMBER.value,
            "required": False,
        }
        experiment.experiment_fields["temperature"] = {
            "name": "Temperature",
            "type": FieldType.NUMBER.value,
            "required": True,
        }
        experiment.experiment_fields["notes"] = {
            "name": "Notes",
            "type": FieldType.TEXT.value,
            "required": False,
        }

        # Should not raise validation error
        experiment.full_clean()
        experiment.save()

        # Verify all fields were added
        experiment.refresh_from_db()
        assert len(experiment.experiment_fields) == 5  # noqa: PLR2004
        assert "ph_level" in experiment.experiment_fields
        assert "temperature" in experiment.experiment_fields
        assert "notes" in experiment.experiment_fields

    def test_mandatory_fields_always_present(self) -> None:
        """Test that mandatory fields are always present."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields=MandatoryFieldSlug.get_mandatory_fields(),
        )

        # Verify mandatory fields exist
        assert "measurement_date" in experiment.experiment_fields
        assert "submitter_email" in experiment.experiment_fields

        # Verify their data
        assert (
            experiment.experiment_fields["measurement_date"]["name"]
            == "Measurement Date"
        )
        assert (
            experiment.experiment_fields["submitter_email"]["name"] == "Submitter Email"
        )

    def test_immutability_check_skipped_for_new_instance(self) -> None:
        """Test that immutability check is skipped for new instances."""
        experiment = Experiment(
            name="New Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldSlug.get_mandatory_fields(),
                "ph_level": {
                    "name": "pH Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                },
            },
        )

        # Should not raise validation error (no pk yet)
        experiment.full_clean()
        experiment.save()

        assert experiment.id is not None

    def test_remove_and_modify_attempts_raise_validation_error(self) -> None:
        """Test that attempting both removal and modification raises error."""
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldSlug.get_mandatory_fields(),
                "ph_level": {
                    "name": "pH Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                },
                "temperature": {
                    "name": "Temperature",
                    "type": FieldType.NUMBER.value,
                    "required": True,
                },
            },
        )

        # Try to remove one field and modify another
        experiment.experiment_fields.pop("ph_level")
        experiment.experiment_fields["temperature"]["name"] = "Modified Temperature"

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict
        # Should mention both removal and modification
        error_message = str(exc_info.value.message_dict)
        assert "Cannot remove" in error_message or "Cannot modify" in error_message

    def test_field_structure_validation(self) -> None:
        """Test that field structure validation works correctly."""
        experiment = Experiment(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                "invalid_slug-123": {  # Invalid slug format
                    "name": "Invalid Field",
                    "type": FieldType.TEXT.value,
                    "required": False,
                },
            },
        )

        with pytest.raises(ValidationError) as exc_info:
            experiment.full_clean()

        assert "experiment_fields" in exc_info.value.message_dict

    def test_field_missing_required_keys(self) -> None:
        """Test that fields missing required keys raise validation error."""
        experiment = Experiment(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                "test_field": {
                    "name": "Test Field",
                    # Missing "type" and "required"
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
        experiment = Experiment(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldSlug.get_mandatory_fields(),
                "test_field": {
                    "name": "Test Field",
                    "type": "invalid_type",
                    "required": False,
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
        experiment = Experiment(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldSlug.get_mandatory_fields(),
                "test_field": {
                    "name": "Test Field",
                    "type": FieldType.TEXT.value,
                    "required": False,
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

    def test_slug_generation_uniqueness(self) -> None:
        """Test that slug generation handles collisions correctly."""
        existing_slugs = {"ph_level", "ph_level_1"}

        # Generate slug for "pH Level" - should get ph_level_2
        slug = Experiment.generate_unique_slug("pH Level", existing_slugs)
        assert slug == "ph_level_2"

        # Generate slug for new field - should get base slug
        slug2 = Experiment.generate_unique_slug("Temperature", existing_slugs)
        assert slug2 == "temperature"

    def test_slug_generation_special_characters(self) -> None:
        """Test that slug generation handles special characters."""
        slug = Experiment.generate_unique_slug("pH Level (Water)", set())
        assert slug == "ph_level_water"

        slug2 = Experiment.generate_unique_slug("123 Field", set())
        assert slug2.startswith(
            "field_"
        )  # Should prefix with "field_" if starts with number

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
        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                **MandatoryFieldSlug.get_mandatory_fields(),
                "ph_level": {
                    "name": "pH Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
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
        fields_dict = {
            "test_field": {
                "name": "Test Field",
                "type": FieldType.TEXT.value,
                "required": False,
            }
        }

        # Should validate directly without {"root": ...} wrapper
        fields_model = ExperimentFieldsDict.model_validate(fields_dict)
        assert "test_field" in fields_model.root
        assert fields_model.root["test_field"].name == "Test Field"

    def test_validation_with_temp_slugs(self) -> None:
        """Test that validation excludes temp slugs (they're processed in save())."""
        experiment = Experiment(
            name="Test Experiment",
            created_by="test@example.com",
            experiment_fields={
                "test_field": {
                    "name": "Test Field",
                    "type": FieldType.TEXT.value,
                    "required": False,
                },
                "temp_123": {
                    "name": "Water Quality",
                    "type": FieldType.TEXT.value,
                    "required": False,
                },
            },
        )

        # Should validate successfully (temp slugs are excluded from validation)
        experiment.full_clean()
        experiment.save()

        # After save, temp slugs should be processed into proper slugs
        experiment.refresh_from_db()
        assert "test_field" in experiment.experiment_fields
        # temp_123 should have been converted to "water_quality" slug
        assert "water_quality" in experiment.experiment_fields
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
        )

        # Should serialize correctly
        dumped = field_def.model_dump(mode="json", exclude_none=True)
        assert dumped["name"] == "Test Field"
        assert dumped["type"] == FieldType.TEXT.value
        assert dumped["required"] is True
        assert "options" not in dumped  # Should be excluded when None

    def test_model_dump_with_options(self) -> None:
        """Test that model_dump() includes options when present."""

        field_def = ExperimentFieldDefinition(
            name="Quality",
            type=FieldType.SELECT,
            required=False,
            options=["Good", "Fair", "Poor"],
        )

        dumped = field_def.model_dump(mode="json", exclude_none=True)
        assert dumped["options"] == ["Good", "Fair", "Poor"]
