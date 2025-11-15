# -*- coding: utf-8 -*-

from __future__ import annotations

import pytest

from speleodb.api.v1.serializers import ExperimentSerializer
from speleodb.api.v1.tests.factories import ExperimentFactory
from speleodb.gis.models import Experiment
from speleodb.gis.models.experiment import FieldType
from speleodb.users.models import User


@pytest.fixture
def user() -> User:
    """Create a test user."""
    return User.objects.create_user(
        email="testuser@example.com",
        password="testpass123",  # noqa: S106
    )


@pytest.mark.django_db
class TestExperimentSerializer:
    """Test cases for ExperimentSerializer."""

    def test_serialize_experiment(self) -> None:
        """Test serializing an experiment to JSON."""
        experiment_fields = {
            "measurement_date": {
                "name": "Measurement Date",
                "type": FieldType.DATE.value,
                "required": True,
            },
            "submitter_email": {
                "name": "Submitter Email",
                "type": FieldType.TEXT.value,
                "required": True,
            },
            "ph_level": {
                "name": "pH Level",
                "type": FieldType.NUMBER.value,
                "required": False,
            },
        }
        experiment = ExperimentFactory.create(
            name="Test Experiment",
            experiment_fields=experiment_fields,
        )

        serializer = ExperimentSerializer(experiment)
        data = serializer.data

        assert data["id"] == str(experiment.id)
        assert data["name"] == "Test Experiment"
        assert isinstance(data["experiment_fields"], list)
        assert len(data["experiment_fields"]) == 3  # noqa: PLR2004

        # Check that fields are in array format with slugs
        field_names = [f["name"] for f in data["experiment_fields"]]
        assert "Measurement Date" in field_names
        assert "Submitter Email" in field_names
        assert "pH Level" in field_names

        # Check slugs are included
        slugs = [f.get("slug") for f in data["experiment_fields"]]
        assert "measurement_date" in slugs
        assert "submitter_email" in slugs
        assert "ph_level" in slugs

    def test_deserialize_experiment_create(self, user: User) -> None:
        """Test creating an experiment from JSON data (array format)."""
        data = {
            "name": "New Experiment",
            "code": "EXP-001",
            "description": "New description",
            "created_by": user.email,
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Submitter Email", "type": "text", "required": True},
                {"name": "pH Level", "type": "number", "required": False},
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"

        saved_experiment = serializer.save()

        assert saved_experiment.name == "New Experiment"
        assert saved_experiment.code == "EXP-001"
        assert saved_experiment.description == "New description"
        assert isinstance(saved_experiment.experiment_fields, dict)
        assert "measurement_date" in saved_experiment.experiment_fields
        assert "submitter_email" in saved_experiment.experiment_fields
        assert "ph_level" in saved_experiment.experiment_fields

    def test_deserialize_with_select_field(self, user: User) -> None:
        """Test creating experiment with select field type."""
        data = {
            "name": "Water Quality Experiment",
            "created_by": user.email,
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Submitter Email", "type": "text", "required": True},
                {
                    "name": "Water Quality",
                    "type": "select",
                    "required": True,
                    "options": ["Good", "Fair", "Poor"],
                },
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"

        saved_experiment = serializer.save()
        water_quality_field = None
        for field_data in saved_experiment.experiment_fields.values():
            if field_data["name"] == "Water Quality":
                water_quality_field = field_data
                break

        assert water_quality_field is not None
        assert water_quality_field["type"] == "select"
        assert water_quality_field["options"] == ["Good", "Fair", "Poor"]

    def test_validate_invalid_field_type(self, user: User) -> None:
        """Test validation fails with invalid field type."""
        data = {
            "name": "Test Experiment",
            "created_by": user.email,
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Invalid Field", "type": "invalid_type", "required": False},
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert not serializer.is_valid()
        assert "experiment_fields" in serializer.errors

    def test_validate_select_field_without_options(self, user: User) -> None:
        """Test validation fails when select field has no options."""
        data = {
            "name": "Test Experiment",
            "created_by": user.email,
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Submitter Email", "type": "text", "required": True},
                {"name": "Quality", "type": "select", "required": False},
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert not serializer.is_valid()
        assert "experiment_fields" in serializer.errors

    def test_validate_options_on_non_select_field(self, user: User) -> None:
        """Test validation fails when non-select field has options."""
        data = {
            "name": "Test Experiment",
            "created_by": user.email,
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {
                    "name": "pH Level",
                    "type": "number",
                    "required": False,
                    "options": ["1", "2", "3"],
                },
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert not serializer.is_valid()
        assert "experiment_fields" in serializer.errors

    def test_validate_missing_field_type(self, user: User) -> None:
        """Test validation fails when field type is missing."""
        data = {
            "name": "Test Experiment",
            "created_by": user.email,
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Invalid Field", "required": False},
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert not serializer.is_valid()
        assert "experiment_fields" in serializer.errors

    def test_validate_empty_field_name(self, user: User) -> None:
        """Test that empty field names are skipped."""
        data = {
            "name": "Test Experiment",
            "created_by": user.email,
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "", "type": "text", "required": False},
                {"name": "Valid Field", "type": "text", "required": False},
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"

        saved_experiment = serializer.save()
        field_names = [
            field_data["name"]
            for field_data in saved_experiment.experiment_fields.values()
        ]
        assert "" not in field_names
        assert "Valid Field" in field_names

    def test_mandatory_fields_always_present(self, user: User) -> None:
        """Test that mandatory fields are always added even if not provided."""
        data = {
            "name": "Test Experiment",
            "created_by": user.email,
            "experiment_fields": [
                {"name": "Custom Field", "type": "text", "required": False},
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"

        saved_experiment = serializer.save()
        assert "measurement_date" in saved_experiment.experiment_fields
        assert "submitter_email" in saved_experiment.experiment_fields
        assert "custom_field" in saved_experiment.experiment_fields

    def test_slug_generation(self, user: User) -> None:
        """Test that slugs are generated correctly."""
        data = {
            "name": "Test Experiment",
            "created_by": user.email,
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "pH Level", "type": "number", "required": False},
                {"name": "Water Temperature", "type": "number", "required": False},
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"

        saved_experiment = serializer.save()
        slugs = list(saved_experiment.experiment_fields.keys())
        assert "measurement_date" in slugs
        assert "ph_level" in slugs
        assert "water_temperature" in slugs

    def test_slug_collision_handling(self, user: User) -> None:
        """Test that slug collisions are handled correctly."""
        data = {
            "name": "Test Experiment",
            "created_by": user.email,
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "pH Level", "type": "number", "required": False},
                {"name": "pH Level", "type": "number", "required": False},  # Duplicate
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"

        saved_experiment = serializer.save()
        slugs = list(saved_experiment.experiment_fields.keys())
        ph_slugs = [s for s in slugs if s.startswith("ph_level")]
        assert len(ph_slugs) == 2  # noqa: PLR2004
        assert "ph_level" in ph_slugs
        assert "ph_level_1" in ph_slugs

    def test_empty_experiment_fields(self, user: User) -> None:
        """Test that empty experiment_fields returns only mandatory fields."""
        data = {
            "name": "Test Experiment",
            "created_by": user.email,
            "experiment_fields": [],
        }

        serializer = ExperimentSerializer(data=data)
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"

        saved_experiment = serializer.save()
        assert len(saved_experiment.experiment_fields) == 2  # noqa: PLR2004
        assert "measurement_date" in saved_experiment.experiment_fields
        assert "submitter_email" in saved_experiment.experiment_fields

    def test_read_only_fields(self) -> None:
        """Test that read-only fields cannot be updated."""
        experiment = ExperimentFactory.create()
        original_id = experiment.id
        original_creation_date = experiment.creation_date

        data = {
            "id": "00000000-0000-0000-0000-000000000000",
            "name": experiment.name,
            "creation_date": "2020-01-01T00:00:00Z",
        }

        serializer = ExperimentSerializer(experiment, data=data, partial=True)
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"
        updated_experiment = serializer.save()

        assert updated_experiment.id == original_id
        assert updated_experiment.creation_date == original_creation_date

    def test_to_representation_empty_dict(self, user: User) -> None:
        """Test that empty dict converts to empty array."""
        # Create experiment with empty dict
        # Note: In practice, the model will add mandatory fields on save,
        # but we test the serializer's handling of empty dict
        experiment = Experiment.objects.create(
            name="Test",
            created_by=user.email,
        )
        # Set experiment_fields to empty dict directly (bypassing save validation)
        Experiment.objects.filter(id=experiment.id).update(experiment_fields={})
        experiment.refresh_from_db()

        serializer = ExperimentSerializer(experiment)
        data = serializer.data

        assert isinstance(data["experiment_fields"], list)
        # Empty dict should serialize to empty list
        assert len(data["experiment_fields"]) == 0

    def test_to_representation_none_fields(self, user: User) -> None:
        """Test that empty experiment_fields converts to empty array."""
        # Note: Model doesn't allow None, so we test with empty dict instead
        experiment = Experiment.objects.create(
            name="Test",
            created_by=user.email,
            experiment_fields={},
        )
        serializer = ExperimentSerializer(experiment)
        data = serializer.data

        assert isinstance(data["experiment_fields"], list)
        assert len(data["experiment_fields"]) == 0
