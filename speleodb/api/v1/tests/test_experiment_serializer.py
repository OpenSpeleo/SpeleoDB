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

        ph_uuid = Experiment.generate_field_uuid()

        experiment_fields = {
            "00000000-0000-0000-0000-000000000001": {
                "name": "Measurement Date",
                "type": FieldType.DATE.value,
                "required": True,
                "order": 0,
            },
            "00000000-0000-0000-0000-000000000002": {
                "name": "Submitter Email",
                "type": FieldType.TEXT.value,
                "required": True,
                "order": 1,
            },
            ph_uuid: {
                "name": "Ph Level",
                "type": FieldType.NUMBER.value,
                "required": False,
                "order": 2,
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

        # Check that fields are in array format with UUIDs
        field_names = [f["name"] for f in data["experiment_fields"]]
        assert "Measurement Date" in field_names
        assert "Submitter Email" in field_names
        assert "Ph Level" in field_names

        # Check IDs are included
        ids = [f.get("id") for f in data["experiment_fields"]]
        assert "00000000-0000-0000-0000-000000000001" in ids
        assert "00000000-0000-0000-0000-000000000002" in ids
        assert ph_uuid in ids

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
                {"name": "Ph Level", "type": "number", "required": False},
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"

        saved_experiment = serializer.save()

        assert saved_experiment.name == "New Experiment"
        assert saved_experiment.code == "EXP-001"
        assert saved_experiment.description == "New description"
        assert isinstance(saved_experiment.experiment_fields, dict)
        assert (
            "00000000-0000-0000-0000-000000000001" in saved_experiment.experiment_fields
        )
        assert (
            "00000000-0000-0000-0000-000000000002" in saved_experiment.experiment_fields
        )
        # Find Ph Level field by name
        ph_uuid = None
        for uuid_str, field_data in saved_experiment.experiment_fields.items():
            if field_data.get("name") == "Ph Level":
                ph_uuid = uuid_str
                break
        assert ph_uuid is not None

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
                    "order": 2,
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
                    "name": "Ph Level",
                    "type": "number",
                    "required": False,
                    "order": 1,
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
        assert (
            "00000000-0000-0000-0000-000000000001" in saved_experiment.experiment_fields
        )
        assert (
            "00000000-0000-0000-0000-000000000002" in saved_experiment.experiment_fields
        )
        # Find custom field by name
        custom_uuid = None
        for uuid_str, field_data in saved_experiment.experiment_fields.items():
            if field_data.get("name") == "Custom Field":
                custom_uuid = uuid_str
                break
        assert custom_uuid is not None

    def test_uuid_generation(self, user: User) -> None:
        """Test that UUIDs are generated correctly."""
        data = {
            "name": "Test Experiment",
            "created_by": user.email,
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Ph Level", "type": "number", "required": False},
                {"name": "Water Temperature", "type": "number", "required": False},
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"

        saved_experiment = serializer.save()
        field_ids = list(saved_experiment.experiment_fields.keys())
        # Check mandatory IDs are present
        assert "00000000-0000-0000-0000-000000000001" in field_ids
        assert "00000000-0000-0000-0000-000000000002" in field_ids
        # Check we have correct number of fields
        assert len(field_ids) == 4  # 2 mandatory + 2 custom  # noqa: PLR2004

    def test_duplicate_name_handling(self, user: User) -> None:
        """Test that duplicate names are rejected (case-insensitive)."""
        data = {
            "name": "Test Experiment",
            "created_by": user.email,
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Ph Level", "type": "number", "required": False},
                {
                    "name": "pH Level",
                    "type": "number",
                    "required": False,
                },  # Duplicate (different case)
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert not serializer.is_valid()
        assert "experiment_fields" in serializer.errors

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
        assert (
            "00000000-0000-0000-0000-000000000001" in saved_experiment.experiment_fields
        )
        assert (
            "00000000-0000-0000-0000-000000000002" in saved_experiment.experiment_fields
        )

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

    def test_name_editing_via_serializer(self, user: User) -> None:
        """Test that field names can be edited via serializer."""
        ph_uuid = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by=user.email,
            experiment_fields={
                "00000000-0000-0000-0000-000000000001": {
                    "name": "Measurement Date",
                    "type": FieldType.DATE.value,
                    "required": True,
                    "order": 0,
                },
                "00000000-0000-0000-0000-000000000002": {
                    "name": "Submitter Email",
                    "type": FieldType.TEXT.value,
                    "required": True,
                    "order": 1,
                },
                ph_uuid: {
                    "name": "Original Name",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
            },
        )

        # Edit the name via serializer
        data = {
            "name": "Test Experiment",
            "experiment_fields": [
                {
                    "id": ph_uuid,
                    "name": "Edited Name",
                    "type": "number",
                    "required": False,
                },
            ],
        }

        serializer = ExperimentSerializer(experiment, data=data, partial=True)
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"
        updated = serializer.save()

        # Verify name was updated
        assert updated.experiment_fields[ph_uuid]["name"] == "Edited Name"

    def test_name_uniqueness_via_serializer(self, user: User) -> None:
        """Test that duplicate names are rejected via serializer."""
        data = {
            "name": "Test Experiment",
            "created_by": user.email,
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Submitter Email", "type": "text", "required": True},
                {"name": "Water Quality", "type": "text", "required": False},
                {
                    "name": "water quality",
                    "type": "number",
                    "required": False,
                    "order": 3,
                },  # Duplicate
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert not serializer.is_valid()
        assert "experiment_fields" in serializer.errors
        assert "not unique" in str(serializer.errors).lower()

    def test_titlecase_enforcement_via_serializer(self, user: User) -> None:
        """Test that titlecase is enforced via serializer."""
        data = {
            "name": "Test Experiment",
            "created_by": user.email,
            "experiment_fields": [
                {"name": "measurement date", "type": "date", "required": True},
                {"name": "SUBMITTER EMAIL", "type": "text", "required": True},
                {"name": "pH level", "type": "number", "required": False},
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"
        saved = serializer.save()

        # Find fields and check titlecase
        fields = saved.experiment_fields
        measurement_field = fields["00000000-0000-0000-0000-000000000001"]
        assert measurement_field["name"] == "Measurement Date"

        submitter_field = fields["00000000-0000-0000-0000-000000000002"]
        assert submitter_field["name"] == "Submitter Email"

        # Find ph level field
        ph_field = next((f for f in fields.values() if "Ph Level" in f["name"]), None)
        assert ph_field is not None
        assert ph_field["name"] == "Ph Level"

    def test_order_field_in_serializer_output(self, user: User) -> None:
        """Test that order field is included in serializer output."""
        ph_uuid = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by=user.email,
            experiment_fields={
                "00000000-0000-0000-0000-000000000001": {
                    "name": "Measurement Date",
                    "type": FieldType.DATE.value,
                    "required": True,
                    "order": 0,
                },
                "00000000-0000-0000-0000-000000000002": {
                    "name": "Submitter Email",
                    "type": FieldType.TEXT.value,
                    "required": True,
                    "order": 1,
                },
                ph_uuid: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 5,
                },
            },
        )

        serializer = ExperimentSerializer(experiment)
        data = serializer.data

        # Find ph level field in output
        ph_field = next(
            (f for f in data["experiment_fields"] if f["id"] == ph_uuid), None
        )
        assert ph_field is not None
        # Order is not exposed in API, but field should be in correct position
        # Since it has order 5, it should be last (after order 0, 1)
        assert data["experiment_fields"][-1]["id"] == ph_uuid

    def test_fields_sorted_by_order_in_output(self, user: User) -> None:
        """Test that fields are sorted by order in serializer output."""
        uuid1 = Experiment.generate_field_uuid()
        uuid2 = Experiment.generate_field_uuid()
        uuid3 = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by=user.email,
            experiment_fields={
                "00000000-0000-0000-0000-000000000001": {
                    "name": "Measurement Date",
                    "type": FieldType.DATE.value,
                    "required": True,
                    "order": 0,
                },
                "00000000-0000-0000-0000-000000000002": {
                    "name": "Submitter Email",
                    "type": FieldType.TEXT.value,
                    "required": True,
                    "order": 1,
                },
                uuid1: {
                    "name": "Field C",
                    "type": FieldType.TEXT.value,
                    "required": False,
                    "order": 10,  # High order
                },
                uuid2: {
                    "name": "Field A",
                    "type": FieldType.TEXT.value,
                    "required": False,
                    "order": 2,  # Low order
                },
                uuid3: {
                    "name": "Field B",
                    "type": FieldType.TEXT.value,
                    "required": False,
                    "order": 5,  # Middle order
                },
            },
        )

        serializer = ExperimentSerializer(experiment)
        data = serializer.data

        # Verify fields are sorted by order
        field_names = [f["name"] for f in data["experiment_fields"]]
        assert field_names == [
            "Measurement Date",
            "Submitter Email",
            "Field A",
            "Field B",
            "Field C",
        ]

    def test_update_field_order_via_serializer(self, user: User) -> None:
        """Test that field order can be updated via serializer."""
        uuid1 = Experiment.generate_field_uuid()

        experiment = Experiment.objects.create(
            name="Test Experiment",
            created_by=user.email,
            experiment_fields={
                "00000000-0000-0000-0000-000000000001": {
                    "name": "Measurement Date",
                    "type": FieldType.DATE.value,
                    "required": True,
                    "order": 0,
                },
                "00000000-0000-0000-0000-000000000002": {
                    "name": "Submitter Email",
                    "type": FieldType.TEXT.value,
                    "required": True,
                    "order": 1,
                },
                uuid1: {
                    "name": "Ph Level",
                    "type": FieldType.NUMBER.value,
                    "required": False,
                    "order": 2,
                },
            },
        )

        # Update order via serializer (by changing position in array)
        # Send ph_uuid field alone - it becomes position 0
        data = {
            "experiment_fields": [
                {"id": uuid1, "name": "Ph Level", "type": "number", "required": False},
            ],
        }

        serializer = ExperimentSerializer(experiment, data=data, partial=True)
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"
        updated = serializer.save()

        # Verify order was updated (in internal storage)
        # Since only ph_uuid field was sent, it merges with existing mandatory fields
        # and gets position based on merge logic
        assert (
            updated.experiment_fields[uuid1]["order"] == 0
        )  # Position in provided array
