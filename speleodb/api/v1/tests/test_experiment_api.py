# -*- coding: utf-8 -*-

from __future__ import annotations

import random
import re
import uuid
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from rest_framework import status

from speleodb.api.v1.serializers import ExperimentSerializer
from speleodb.api.v1.tests.base_testcase import BaseAPITestCase
from speleodb.api.v1.tests.factories import ExperimentFactory
from speleodb.api.v1.tests.factories import UserExperimentPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Experiment
from speleodb.gis.models.experiment import FieldType
from speleodb.users.models import User

if TYPE_CHECKING:
    from typing import Any


@pytest.fixture
def user() -> User:
    """Create a test user."""
    return User.objects.create_user(
        email="testuser@example.com",
        password="testpass123",  # noqa: S106
    )


@pytest.mark.django_db
class TestExperimentAPI(BaseAPITestCase):
    """Test cases for Experiment API endpoints."""

    def test_get_experiments_requires_authentication(self) -> None:
        """Test that GET endpoint requires authentication."""
        client = BaseAPITestCase.client_class()
        response = client.get(reverse("api:v1:experiments"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_post_experiments_requires_authentication(self) -> None:
        """Test that POST endpoint requires authentication."""
        client = BaseAPITestCase.client_class()
        data = {
            "name": "Test Experiment",
            "experiment_fields": [],
        }
        response = client.post(
            reverse("api:v1:experiments"),
            data=data,
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_experiments_list(self) -> None:
        """Test GET endpoint returns list of experiments."""
        # Create test experiments
        exp1 = ExperimentFactory.create(name="Experiment 1", created_by=self.user.email)
        exp2 = ExperimentFactory.create(name="Experiment 2", created_by=self.user.email)

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=exp1,
            level=PermissionLevel.READ_ONLY,
        )
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=exp2,
            level=PermissionLevel.READ_ONLY,
        )

        response = self.client.get(
            reverse("api:v1:experiments"), headers={"authorization": self.auth}
        )

        assert response.status_code == status.HTTP_200_OK
        assert "data" in response.json()
        data = response.json()["data"]
        assert isinstance(data, list)
        assert len(data) >= 2  # noqa: PLR2004

        # Check that experiments are in the response
        experiment_names = [exp["name"] for exp in data]
        assert "Experiment 1" in experiment_names
        assert "Experiment 2" in experiment_names

    def test_get_experiments_format(self) -> None:
        """Test GET endpoint returns correct format."""
        experiment = ExperimentFactory.create(
            name="Test Experiment",
            code="EXP-001",
            description="Test description",
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_ONLY,
        )

        response = self.client.get(
            reverse("api:v1:experiments"), headers={"authorization": self.auth}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]

        # Find our experiment
        exp_data = next((e for e in data if e["id"] == str(experiment.id)), None)
        assert exp_data is not None

        # Check structure
        assert "id" in exp_data
        assert "name" in exp_data
        assert "code" in exp_data
        assert "description" in exp_data
        assert "created_by" in exp_data
        assert "experiment_fields" in exp_data
        assert "creation_date" in exp_data
        assert "modified_date" in exp_data

        # Check experiment_fields is array format
        assert isinstance(exp_data["experiment_fields"], list)

    def test_post_create_experiment(self) -> None:
        """Test POST endpoint creates experiment successfully."""
        data = {
            "name": "New Experiment",
            "code": "EXP-999",
            "description": "New experiment description",
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Submitter Email", "type": "text", "required": True},
                {"name": "Ph Level", "type": "number", "required": False},
            ],
        }

        response = self.client.post(
            reverse("api:v1:experiments"),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()["data"]

        assert response_data["name"] == "New Experiment"
        assert response_data["code"] == "EXP-999"
        assert response_data["description"] == "New experiment description"
        assert response_data["created_by"] == self.user.email

        # Check experiment_fields format
        assert isinstance(response_data["experiment_fields"], list)
        assert len(response_data["experiment_fields"]) == 3  # noqa: PLR2004

        # Verify experiment was saved to database
        experiment = Experiment.objects.get(id=response_data["id"])
        assert experiment.name == "New Experiment"
        assert isinstance(experiment.experiment_fields, dict)
        assert "00000000-0000-0000-0000-000000000001" in experiment.experiment_fields
        # Find Ph Level field by name
        ph_uuid = next(
            (
                k
                for k, v in experiment.experiment_fields.items()
                if v["name"] == "Ph Level"
            ),
            None,
        )
        assert ph_uuid is not None

    def test_post_create_experiment_with_select_field(self) -> None:
        """Test POST endpoint with select field type."""
        data = {
            "name": "Water Quality Experiment",
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Submitter Email", "type": "text", "required": True},
                {
                    "name": "Quality",
                    "type": "select",
                    "required": True,
                    "order": 2,
                    "options": ["Excellent", "Good", "Fair", "Poor"],
                },
            ],
        }

        response = self.client.post(
            reverse("api:v1:experiments"),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()["data"]

        # Find quality field
        quality_field = next(
            (f for f in response_data["experiment_fields"] if f["name"] == "Quality"),
            None,
        )
        assert quality_field is not None
        assert quality_field["type"] == "select"
        assert quality_field["options"] == ["Excellent", "Good", "Fair", "Poor"]

    def test_post_invalid_field_type(self) -> None:
        """Test POST endpoint rejects invalid field type."""
        data = {
            "name": "Test Experiment",
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Invalid Field", "type": "invalid_type", "required": False},
            ],
        }

        response = self.client.post(
            reverse("api:v1:experiments"),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.json()

    def test_post_missing_required_name(self) -> None:
        """Test POST endpoint rejects missing name."""
        data = {
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
            ],
        }

        response = self.client.post(
            reverse("api:v1:experiments"),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.json()

    def test_post_select_field_without_options(self) -> None:
        """Test POST endpoint rejects select field without options."""
        data = {
            "name": "Test Experiment",
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Quality", "type": "select", "required": False},
            ],
        }

        response = self.client.post(
            reverse("api:v1:experiments"),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.json()

    def test_post_options_on_non_select_field(self) -> None:
        """Test POST endpoint rejects options on non-select field."""
        data = {
            "name": "Test Experiment",
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

        response = self.client.post(
            reverse("api:v1:experiments"),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.json()

    def test_post_empty_experiment_fields(self) -> None:
        """Test POST endpoint with empty experiment_fields."""
        data = {
            "name": "Test Experiment",
            "experiment_fields": [],
        }

        response = self.client.post(
            reverse("api:v1:experiments"),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()["data"]

        # Should have mandatory fields
        assert len(response_data["experiment_fields"]) == 2  # noqa: PLR2004
        field_names = [f["name"] for f in response_data["experiment_fields"]]
        assert "Measurement Date" in field_names
        assert "Submitter Email" in field_names

    def test_post_created_by_set_from_user(self) -> None:
        """Test that created_by is set from authenticated user."""
        data = {
            "name": "Test Experiment",
            "experiment_fields": [],
        }

        response = self.client.post(
            reverse("api:v1:experiments"),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()["data"]
        assert response_data["created_by"] == self.user.email

        # Verify in database
        experiment = Experiment.objects.get(id=response_data["id"])
        assert experiment.created_by == self.user.email


@pytest.mark.django_db
class TestExperimentAPIFuzzy:
    """Fuzzy testing for Experiment API to verify error handling."""

    def test_fuzzy_invalid_json(self) -> None:
        """Test API handles invalid JSON gracefully."""
        # Test serializer level validation
        serializer = ExperimentSerializer(data={"invalid": "json"})
        assert not serializer.is_valid()

    def test_fuzzy_malformed_field_data(self) -> None:
        """Test serializer handles malformed field data."""
        test_cases: list[dict[str, Any]] = [
            # Not a list
            {"experiment_fields": "not a list"},
            # Not a dict in list
            {"experiment_fields": ["not a dict"]},
            # Missing required keys
            {"experiment_fields": [{"name": "Test"}]},
            # Invalid types
            {"experiment_fields": [{"name": 123, "type": "text", "required": False}]},
            {"experiment_fields": [{"name": "Test", "type": 123, "required": False}]},
            {
                "experiment_fields": [
                    {"name": "Test", "type": "text", "required": "yes"}
                ]
            },
        ]

        for test_data in test_cases:
            serializer_data: dict[str, Any] = {"name": "Test"}
            serializer_data.update(test_data)
            serializer = ExperimentSerializer(data=serializer_data)
            # Some might be valid after conversion, but we check structure
            if "experiment_fields" in test_data:
                experiment_fields = test_data["experiment_fields"]
                if isinstance(experiment_fields, list):
                    for field in experiment_fields:
                        if not isinstance(field, dict):
                            assert not serializer.is_valid() or any(
                                "experiment_fields" in str(err).lower()
                                for err in serializer.errors.values()
                            )

    def test_fuzzy_extreme_field_names(self, user: User) -> None:
        """Test serializer handles extreme field names."""
        test_cases = [
            {"name": "A" * 1000, "type": "text", "required": False},  # Very long name
            {"name": "   ", "type": "text", "required": False},  # Only whitespace
            {"name": "!@#$%^&*()", "type": "text", "required": False},  # Special chars
            {"name": "123", "type": "text", "required": False},  # Starts with number
        ]

        for field_data in test_cases:
            data = {
                "name": "Test Experiment",
                "created_by": user.email,
                "experiment_fields": [
                    {"name": "Measurement Date", "type": "date", "required": True},
                    field_data,
                ],
            }
            serializer = ExperimentSerializer(data=data)
            # Should handle gracefully (either valid or clear error)
            field_name = field_data.get("name", "")
            if isinstance(field_name, str) and field_name.strip() == "":
                # Empty names should be skipped
                if serializer.is_valid():
                    saved = serializer.save()
                    field_names = [f["name"] for f in saved.experiment_fields.values()]
                    assert field_name not in field_names

    def test_fuzzy_all_field_types(self, user: User) -> None:
        """Test all valid field types work correctly."""
        valid_types = FieldType.get_all_types()

        for field_type in valid_types:
            field_data = {
                "name": f"Test {field_type}",
                "type": field_type,
                "required": False,
                "order": 2,
            }

            # Add options for select type
            if field_type == FieldType.SELECT.value:
                field_data["options"] = ["Option 1", "Option 2"]

            data = {
                "name": "Test Experiment",
                "created_by": user.email,
                "experiment_fields": [
                    {"name": "Measurement Date", "type": "date", "required": True},
                    {"name": "Submitter Email", "type": "text", "required": True},
                    field_data,
                ],
            }

            serializer = ExperimentSerializer(data=data)
            assert serializer.is_valid(), (
                f"Field type {field_type} failed: {serializer.errors}"
            )

            saved = serializer.save()
            assert isinstance(saved.experiment_fields, dict)

    def test_fuzzy_many_fields(self, user: User) -> None:
        """Test serializer handles many fields."""
        fields: list[dict[str, str | bool | int]] = [
            {"name": "Measurement Date", "type": "date", "required": True},
            {"name": "Submitter Email", "type": "text", "required": True},
        ]

        # Add 100 custom fields
        for i in range(100):
            field_type = random.choice(FieldType.get_all_types())
            field: dict[str, str | bool | int | list[str]] = {
                "name": f"Field {i}",
                "type": field_type,
                "required": random.choice([True, False]),
                "order": i + 2,
            }
            # Add options for select type
            if field_type == FieldType.SELECT.value:
                field["options"] = [f"Option {j}" for j in range(1, 4)]
            fields.append(field)  # type: ignore[arg-type]

        data = {
            "name": "Large Experiment",
            "created_by": user.email,
            "experiment_fields": fields,
        }

        serializer = ExperimentSerializer(data=data)
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"

        saved = serializer.save()
        # Should have 2 mandatory + 100 custom = 102 fields
        assert len(saved.experiment_fields) == 102  # noqa: PLR2004

    def test_fuzzy_unicode_field_names(self, user: User) -> None:
        """Test serializer handles unicode in field names."""
        data = {
            "name": "Unicode Test",
            "created_by": user.email,
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Submitter Email", "type": "text", "required": True},
                {"name": "Ph Niveau", "type": "number", "required": False},  # French
                {"name": "温度", "type": "number", "required": False},  # Chinese
                {
                    "name": "температура",
                    "type": "number",
                    "required": False,
                    "order": 4,
                },  # Cyrillic
            ],
        }

        serializer = ExperimentSerializer(data=data)
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"

        saved = serializer.save()
        # All fields should be present
        assert len(saved.experiment_fields) >= 5  # noqa: PLR2004


@pytest.mark.django_db
class TestExperimentSpecificAPI(BaseAPITestCase):
    """Test cases for ExperimentSpecificApiView (GET, PUT, PATCH, DELETE)."""

    def test_get_experiment_detail_requires_authentication(self) -> None:
        """Test that GET detail endpoint requires authentication."""
        experiment = ExperimentFactory.create(created_by=self.user.email)

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_ONLY,
        )

        client = BaseAPITestCase.client_class()
        response = client.get(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_experiment_detail(self) -> None:
        """Test GET endpoint retrieves a specific experiment."""
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
            code="EXP-001",
            description="Test description",
            experiment_fields=experiment_fields,
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_ONLY,
        )

        response = self.client.get(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "data" in response.json()
        data = response.json()["data"]

        assert data["id"] == str(experiment.id)
        assert data["name"] == "Test Experiment"
        assert data["code"] == "EXP-001"
        assert data["description"] == "Test description"
        assert data["created_by"] == self.user.email
        assert isinstance(data["experiment_fields"], list)
        assert len(data["experiment_fields"]) == 3  # noqa: PLR2004

    def test_get_nonexistent_experiment(self) -> None:
        """Test GET endpoint returns 404 for nonexistent experiment."""
        nonexistent_id = uuid.uuid4()
        response = self.client.get(
            reverse("api:v1:experiment-detail", kwargs={"id": nonexistent_id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_put_update_experiment_requires_authentication(self) -> None:
        """Test that PUT endpoint requires authentication."""
        experiment = ExperimentFactory.create(created_by=self.user.email)

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_ONLY,
        )

        client = BaseAPITestCase.client_class()
        data = {"name": "Updated Name"}
        response = client.put(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_put_update_experiment_basic_fields(self) -> None:
        """Test PUT endpoint updates experiment basic fields."""
        original_email = "original@example.com"
        experiment = ExperimentFactory.create(
            name="Original Name",
            code="OLD-001",
            description="Original description",
            created_by=original_email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        data = {
            "name": "Updated Name",
            "code": "NEW-001",
            "description": "Updated description",
            "is_active": False,
            "experiment_fields": [],
        }

        response = self.client.put(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        assert response_data["name"] == "Updated Name"
        assert response_data["code"] == "NEW-001"
        assert response_data["description"] == "Updated description"
        assert response_data["is_active"] is False
        # created_by should remain unchanged (read-only)
        assert response_data["created_by"] == original_email

        # Verify in database
        experiment.refresh_from_db()
        assert experiment.name == "Updated Name"
        assert experiment.code == "NEW-001"
        assert experiment.description == "Updated description"
        assert experiment.is_active is False
        assert experiment.created_by == original_email  # Should not change

    def test_put_add_new_fields(self) -> None:
        """Test PUT endpoint can add new fields to existing experiment."""
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
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Add new fields
        data = {
            "name": "Test Experiment",
            "experiment_fields": [
                {"name": "Water Temperature", "type": "number", "required": False},
                {
                    "name": "Quality Rating",
                    "type": "select",
                    "required": True,
                    "order": 4,
                    "options": ["Excellent", "Good", "Fair"],
                },
            ],
        }

        response = self.client.put(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        # Should have original 3 fields + 2 new fields = 5 total
        assert len(response_data["experiment_fields"]) == 5  # noqa: PLR2004

        field_names = [f["name"] for f in response_data["experiment_fields"]]
        assert "Ph Level" in field_names  # Original field preserved
        assert "Water Temperature" in field_names  # New field added
        assert "Quality Rating" in field_names  # New field added

        # Verify in database
        experiment.refresh_from_db()
        assert len(experiment.experiment_fields) == 5  # noqa: PLR2004

    def test_put_cannot_modify_existing_field(self) -> None:
        """Test PUT endpoint cannot modify existing field properties."""
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
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Try to modify existing field (change type from number to text)
        data = {
            "name": "Test Experiment",
            "experiment_fields": [
                {
                    "id": ph_uuid,
                    "name": "Ph Level",
                    "type": "text",
                    "required": False,
                },  # Changed type
            ],
        }

        response = self.client.put(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.json()
        # Should have immutability error
        errors = response.json()["errors"]
        assert "experiment_fields" in errors or any(
            "immutable" in str(err).lower() or "modify" in str(err).lower()
            for err in errors.values()
        )

    def test_put_cannot_remove_existing_field(self) -> None:
        """Test PUT endpoint cannot remove existing fields."""
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
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Try to remove ph_level field (only send mandatory fields, omit ph_uuid)
        data = {
            "name": "Test Experiment",
            "experiment_fields": [
                {
                    "uuid": "00000000-0000-0000-0000-000000000001",
                    "name": "Measurement Date",
                    "type": "date",
                    "required": True,
                },
                {
                    "uuid": "00000000-0000-0000-0000-000000000002",
                    "name": "Submitter Email",
                    "type": "text",
                    "required": True,
                },
                # ph_uuid intentionally omitted - should trigger removal error
            ],
        }

        response = self.client.put(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.json()
        # Should have immutability error about removing fields
        errors = response.json()["errors"]
        assert "experiment_fields" in errors or any(
            "remove" in str(err).lower() or "immutable" in str(err).lower()
            for err in errors.values()
        )

    def test_patch_partial_update(self) -> None:
        """Test PATCH endpoint allows partial updates."""
        experiment = ExperimentFactory.create(
            name="Original Name",
            code="OLD-001",
            description="Original description",
            is_active=True,
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Only update name
        data = {"name": "Updated Name"}

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        assert response_data["name"] == "Updated Name"
        assert response_data["code"] == "OLD-001"  # Unchanged
        assert response_data["description"] == "Original description"  # Unchanged
        assert response_data["is_active"] is True  # Unchanged

    def test_patch_add_new_fields(self) -> None:
        """Test PATCH endpoint can add new fields."""
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
        }
        experiment = ExperimentFactory.create(
            name="Test Experiment",
            experiment_fields=experiment_fields,
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Add new field via PATCH
        data = {
            "experiment_fields": [
                {"name": "New Field", "type": "text", "required": False},
            ],
        }

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        # Should have 2 original + 1 new = 3 fields
        assert len(response_data["experiment_fields"]) == 3  # noqa: PLR2004

        field_names = [f["name"] for f in response_data["experiment_fields"]]
        assert "Measurement Date" in field_names
        assert "Submitter Email" in field_names
        assert "New Field" in field_names

    def test_patch_cannot_modify_existing_field(self) -> None:
        """Test PATCH endpoint cannot modify existing field."""
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
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Try to modify existing field via PATCH
        data = {
            "experiment_fields": [
                {
                    "id": ph_uuid,
                    "name": "Ph Level",
                    "type": "text",
                    "required": True,
                },  # Changed type
            ],
        }

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.json()

    def test_delete_requires_authentication(self) -> None:
        """Test that DELETE endpoint requires authentication."""
        experiment = ExperimentFactory.create(created_by=self.user.email)

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        client = BaseAPITestCase.client_class()

        response = client.delete(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_deactivates_experiment(self) -> None:
        """Test DELETE endpoint deactivates experiment instead of deleting."""
        experiment = ExperimentFactory.create(
            name="Test Experiment",
            is_active=True,
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.ADMIN,
        )

        experiment_id = experiment.id

        response = self.client.delete(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]
        assert response_data["id"] == str(experiment_id)
        assert "message" in response_data

        # Verify experiment still exists but is deactivated
        experiment.refresh_from_db()
        assert experiment.is_active is False
        assert Experiment.objects.filter(id=experiment_id).exists()

    def test_delete_preserves_experiment_fields(self) -> None:
        """Test DELETE preserves experiment fields when deactivating."""
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
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.ADMIN,
        )

        response = self.client.delete(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify fields are preserved
        experiment.refresh_from_db()
        assert len(experiment.experiment_fields) == 3  # noqa: PLR2004
        assert ph_uuid in experiment.experiment_fields

    def test_put_invalid_field_type(self) -> None:
        """Test PUT endpoint rejects invalid field type."""
        experiment = ExperimentFactory.create(created_by=self.user.email)

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        data = {
            "name": "Test Experiment",
            "experiment_fields": [
                {"name": "Invalid Field", "type": "invalid_type", "required": False},
            ],
        }

        response = self.client.put(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.json()

    def test_patch_update_is_active(self) -> None:
        """Test PATCH can update is_active field."""
        experiment = ExperimentFactory.create(
            name="Test Experiment",
            is_active=True,
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        data = {"is_active": False}

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]
        assert response_data["is_active"] is False

        experiment.refresh_from_db()
        assert experiment.is_active is False

    def test_put_update_with_select_field_options(self) -> None:
        """Test PUT can add new select field with options."""
        experiment = ExperimentFactory.create(created_by=self.user.email)

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        data = {
            "name": "Test Experiment",
            "experiment_fields": [
                {
                    "name": "Quality",
                    "type": "select",
                    "required": True,
                    "options": ["Excellent", "Good", "Fair", "Poor"],
                },
            ],
        }

        response = self.client.put(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        # Find quality field
        quality_field = next(
            (f for f in response_data["experiment_fields"] if f["name"] == "Quality"),
            None,
        )
        assert quality_field is not None
        assert quality_field["type"] == "select"
        assert quality_field["options"] == ["Excellent", "Good", "Fair", "Poor"]

    def test_put_cannot_modify_created_by(self) -> None:
        """Test PUT endpoint cannot modify created_by field (read-only)."""
        original_email = "original@example.com"
        experiment = ExperimentFactory.create(created_by=original_email)

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Try to change created_by
        data = {
            "name": "Test Experiment",
            "created_by": "newemail@example.com",  # Should be ignored
            "experiment_fields": [],
        }

        response = self.client.put(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        # created_by should remain unchanged
        assert response_data["created_by"] == original_email

        # Verify in database
        experiment.refresh_from_db()
        assert experiment.created_by == original_email

    def test_patch_cannot_modify_created_by(self) -> None:
        """Test PATCH endpoint cannot modify created_by field (read-only)."""
        original_email = "original@example.com"
        experiment = ExperimentFactory.create(created_by=original_email)

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Try to change created_by via PATCH
        data = {"created_by": "newemail@example.com"}  # Should be ignored

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        # created_by should remain unchanged
        assert response_data["created_by"] == original_email

        # Verify in database
        experiment.refresh_from_db()
        assert experiment.created_by == original_email

    def test_put_end_date_can_be_empty(self) -> None:
        """Test PUT endpoint allows empty end_date."""
        experiment = ExperimentFactory.create(
            name="Test Experiment",
            start_date="2024-01-01",
            end_date="2024-12-31",
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        data = {
            "name": "Test Experiment",
            "end_date": "",  # Empty string should be converted to None
            "experiment_fields": [],
        }

        response = self.client.put(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        # end_date should be None/null
        assert response_data["end_date"] is None

        # Verify in database
        experiment.refresh_from_db()
        assert experiment.end_date is None

    def test_patch_end_date_can_be_empty(self) -> None:
        """Test PATCH endpoint allows empty end_date."""
        experiment = ExperimentFactory.create(
            name="Test Experiment",
            start_date="2024-01-01",
            end_date="2024-12-31",
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        data = {"end_date": ""}  # Empty string should be converted to None

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        # end_date should be None/null
        assert response_data["end_date"] is None

        # Verify in database
        experiment.refresh_from_db()
        assert experiment.end_date is None

    def test_put_end_date_before_start_date_violates_constraint(self) -> None:
        """Test PUT endpoint rejects end_date before start_date."""
        experiment = ExperimentFactory.create(
            name="Test Experiment",
            start_date="2024-01-01",
            end_date="2024-12-31",
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Try to set end_date before start_date
        data = {
            "name": "Test Experiment",
            "start_date": "2024-12-31",
            "end_date": "2024-01-01",  # Before start_date
            "experiment_fields": [],
        }

        response = self.client.put(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.json()

        errors = response.json()["errors"]
        # Should have error on end_date field
        assert "end_date" in errors
        assert any(
            "greater than or equal to start_date" in str(err).lower()
            for err in errors["end_date"]
        )

    def test_patch_end_date_before_start_date_violates_constraint(self) -> None:
        """Test PATCH endpoint rejects end_date before start_date."""
        experiment = ExperimentFactory.create(
            name="Test Experiment",
            start_date="2024-12-31",
            end_date="2024-12-31",
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Try to set end_date before start_date via PATCH
        data = {
            "start_date": "2024-12-31",
            "end_date": "2024-01-01",  # Before start_date
        }

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.json()

        errors = response.json()["errors"]
        # Should have error on end_date field
        assert "end_date" in errors
        assert any(
            "greater than or equal to start_date" in str(err).lower()
            for err in errors["end_date"]
        )

    def test_post_end_date_without_start_date_violates_constraint(self) -> None:
        """Test POST endpoint rejects end_date without start_date."""
        data = {
            "name": "Test Experiment",
            "end_date": "2024-12-31",  # No start_date provided
            "experiment_fields": [],
        }

        response = self.client.post(
            reverse("api:v1:experiments"),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.json()

        errors = response.json()["errors"]
        # Should have error on end_date field
        assert "end_date" in errors
        assert any(
            "start_date must also be provided" in str(err).lower()
            or "start_date must be provided" in str(err).lower()
            for err in errors["end_date"]
        )

    def test_put_end_date_without_start_date_violates_constraint(self) -> None:
        """Test PUT endpoint rejects end_date without start_date."""
        experiment = ExperimentFactory.create(
            name="Test Experiment",
            start_date="2024-01-01",
            end_date="2024-12-31",
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Try to set end_date without start_date (explicitly set start_date to empty)
        data = {
            "name": "Test Experiment",
            "start_date": "",  # Explicitly remove start_date
            "end_date": "2024-12-31",
            "experiment_fields": [],
        }

        response = self.client.put(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.json()

        errors = response.json()["errors"]
        # Should have error on end_date field
        assert "end_date" in errors
        assert any(
            "start_date must also be provided" in str(err).lower()
            or "start_date must be provided" in str(err).lower()
            for err in errors["end_date"]
        )

    def test_patch_end_date_without_start_date_violates_constraint(self) -> None:
        """Test PATCH endpoint rejects end_date without start_date."""
        experiment = ExperimentFactory.create(
            name="Test Experiment",
            start_date="2024-01-01",
            end_date="2024-12-31",
            created_by=self.user.email,
        )

        # Create permissions
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # First, remove end_date via PATCH (so we can remove start_date)
        self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data={"end_date": ""},  # Remove end_date first
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        # Then remove start_date via PATCH
        self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data={"start_date": ""},  # Remove start_date
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        # Now try to set end_date without start_date via PATCH
        data = {"end_date": "2024-12-31"}  # No start_date

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.json()

        errors = response.json()["errors"]
        # Should have error on end_date field
        assert "end_date" in errors
        assert any(
            "start_date must also be provided" in str(err).lower()
            or "start_date must be provided" in str(err).lower()
            for err in errors["end_date"]
        )


@pytest.mark.django_db
class TestExperimentFieldNameEditing(BaseAPITestCase):
    """Test cases for editing field names via API."""

    def test_patch_edit_field_name(self) -> None:
        """Test PATCH endpoint can edit field name."""
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
                "name": "Original Name",
                "type": FieldType.NUMBER.value,
                "required": False,
                "order": 2,
            },
        }

        experiment = ExperimentFactory.create(
            name="Test Experiment",
            experiment_fields=experiment_fields,
            created_by=self.user.email,
        )

        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Edit field name
        data = {
            "experiment_fields": [
                {
                    "id": ph_uuid,
                    "name": "Edited Name",
                    "type": "number",
                    "required": False,
                },
            ],
        }

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        # Find the field and verify name was changed
        edited_field = next(
            (f for f in response_data["experiment_fields"] if f["id"] == ph_uuid), None
        )
        assert edited_field is not None
        assert edited_field["name"] == "Edited Name"

        # Verify in database
        experiment.refresh_from_db()
        assert experiment.experiment_fields[ph_uuid]["name"] == "Edited Name"

    def test_patch_edit_field_name_enforces_titlecase(self) -> None:
        """Test that edited field names are converted to titlecase."""
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
                "name": "Original",
                "type": FieldType.NUMBER.value,
                "required": False,
                "order": 2,
            },
        }

        experiment = ExperimentFactory.create(
            name="Test Experiment",
            experiment_fields=experiment_fields,
            created_by=self.user.email,
        )

        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Edit field name with lowercase
        data = {
            "experiment_fields": [
                {
                    "id": ph_uuid,
                    "name": "new lowercase name",
                    "type": "number",
                    "required": False,
                },
            ],
        }

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        # Find the field and verify name was titlecased
        edited_field = next(
            (f for f in response_data["experiment_fields"] if f["id"] == ph_uuid), None
        )
        assert edited_field is not None
        assert edited_field["name"] == "New Lowercase Name"

    def test_patch_edit_name_to_duplicate_rejected(self) -> None:
        """Test that editing a name to duplicate another is rejected."""
        uuid1 = Experiment.generate_field_uuid()
        uuid2 = Experiment.generate_field_uuid()

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
            uuid1: {
                "name": "Water Quality",
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
        }

        experiment = ExperimentFactory.create(
            name="Test Experiment",
            experiment_fields=experiment_fields,
            created_by=self.user.email,
        )

        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Try to edit uuid2's name to match uuid1
        data = {
            "experiment_fields": [
                {
                    "id": uuid2,
                    "name": "Water Quality",
                    "type": "number",
                    "required": False,
                },
            ],
        }

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.json()
        errors = response.json()["errors"]
        assert "experiment_fields" in errors
        assert "not unique" in str(errors).lower()


@pytest.mark.django_db
class TestExperimentFieldOrdering(BaseAPITestCase):
    """Test cases for field ordering functionality."""

    def test_patch_reorder_fields(self) -> None:
        """Test PATCH endpoint can reorder fields."""
        uuid1 = Experiment.generate_field_uuid()
        uuid2 = Experiment.generate_field_uuid()

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
            uuid1: {
                "name": "Field A",
                "type": FieldType.TEXT.value,
                "required": False,
                "order": 2,
            },
            uuid2: {
                "name": "Field B",
                "type": FieldType.TEXT.value,
                "required": False,
                "order": 3,
            },
        }

        experiment = ExperimentFactory.create(
            name="Test Experiment",
            experiment_fields=experiment_fields,
            created_by=self.user.email,
        )

        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Swap order of Field A and Field B by changing their position in array
        # Position in array = order (no explicit order field)
        data = {
            "experiment_fields": [
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "name": "Measurement Date",
                    "type": "date",
                    "required": True,
                },
                {
                    "id": "00000000-0000-0000-0000-000000000002",
                    "name": "Submitter Email",
                    "type": "text",
                    "required": True,
                },
                {
                    "id": uuid2,
                    "name": "Field B",
                    "type": "text",
                    "required": False,
                },  # Now position 2
                {
                    "id": uuid1,
                    "name": "Field A",
                    "type": "text",
                    "required": False,
                },  # Now position 3
            ],
        }

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        # Verify order changed and fields are sorted
        field_names = [f["name"] for f in response_data["experiment_fields"]]
        # Should be:
        # Measurement Date (0), Submitter Email (1), Field B (5), Field A (10)
        assert field_names == [
            "Measurement Date",
            "Submitter Email",
            "Field B",
            "Field A",
        ]

    def test_post_fields_without_order_auto_assigns(self) -> None:
        """Test that fields without order get auto-assigned values."""
        data = {
            "name": "Test Experiment",
            "experiment_fields": [
                {
                    "name": "Measurement Date",
                    "type": "date",
                    "required": True,
                },  # No order
                {
                    "name": "Submitter Email",
                    "type": "text",
                    "required": True,
                },  # No order
                {"name": "Custom Field", "type": "text", "required": False},  # No order
            ],
        }

        response = self.client.post(
            reverse("api:v1:experiments"),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()["data"]

        # All fields should have order assigned
        for field in response_data["experiment_fields"]:
            assert "order" in field
            assert isinstance(field["order"], int)
            assert field["order"] >= 0

    def test_patch_only_order_without_other_changes(self) -> None:
        """Test PATCH can update only order without changing other properties."""
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
            created_by=self.user.email,
        )

        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Update only order (by changing position in array)
        # Put ph_uuid field at the end of the array to give it a higher order
        data = {
            "experiment_fields": [
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "name": "Measurement Date",
                    "type": "date",
                    "required": True,
                },
                {
                    "id": "00000000-0000-0000-0000-000000000002",
                    "name": "Submitter Email",
                    "type": "text",
                    "required": True,
                },
                {
                    "id": ph_uuid,
                    "name": "Ph Level",
                    "type": "number",
                    "required": False,
                },  # Position 2 = order 2
            ],
        }

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        # Find the field and verify it's in the correct position
        field = next(
            (f for f in response_data["experiment_fields"] if f["id"] == ph_uuid), None
        )
        assert field is not None
        # Order is implicit from position - ph_uuid should be at position 2
        # (after 2 mandatory fields)
        assert field["name"] == "Ph Level"
        assert field["type"] == "number"
        assert field["required"] is False
        # Verify it's at expected position in array
        field_index = response_data["experiment_fields"].index(field)
        assert field_index == 2  # Position 2 = order 2  # noqa: PLR2004


@pytest.mark.django_db
class TestExperimentFieldUuidSystem(BaseAPITestCase):
    """Test cases for UUID-based field system."""

    def test_get_response_includes_uuids(self) -> None:
        """Test that GET response includes UUID for each field."""
        experiment = ExperimentFactory.create(created_by=self.user.email)

        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_ONLY,
        )

        response = self.client.get(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        # Every field should have a UUID
        for field in response_data["experiment_fields"]:
            assert "id" in field
            # UUID should be valid format
            uuid_pattern = (
                r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            )
            assert re.match(uuid_pattern, field["id"], re.IGNORECASE)

    def test_mandatory_fields_have_fixed_uuids(self) -> None:
        """Test that mandatory fields always have the same UUIDs."""
        exp1 = ExperimentFactory.create(name="Experiment 1", created_by=self.user.email)
        exp2 = ExperimentFactory.create(name="Experiment 2", created_by=self.user.email)

        # Both should have same mandatory UUIDs
        assert "00000000-0000-0000-0000-000000000001" in exp1.experiment_fields
        assert "00000000-0000-0000-0000-000000000002" in exp1.experiment_fields
        assert "00000000-0000-0000-0000-000000000001" in exp2.experiment_fields
        assert "00000000-0000-0000-0000-000000000002" in exp2.experiment_fields

    def test_custom_fields_have_unique_uuids(self) -> None:
        """Test that custom fields get unique UUIDs."""
        data = {
            "name": "Test Experiment",
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Submitter Email", "type": "text", "required": True},
                {"name": "Field A", "type": "text", "required": False},
                {"name": "Field B", "type": "text", "required": False},
            ],
        }

        response = self.client.post(
            reverse("api:v1:experiments"),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()["data"]

        # Collect all UUIDs
        uuids = [f["id"] for f in response_data["experiment_fields"]]

        # All UUIDs should be unique
        assert len(uuids) == len(set(uuids))

    def test_uuid_immutable_via_api(self) -> None:
        """Test that UUID cannot be changed via API."""
        ph_uuid = Experiment.generate_field_uuid()
        new_uuid = Experiment.generate_field_uuid()

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
            created_by=self.user.email,
        )

        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Try to provide a field with the new UUID but same name
        # This should be treated as adding a new field, not changing UUID
        data = {
            "experiment_fields": [
                {
                    "uuid": new_uuid,
                    "name": "Ph Level",
                    "type": "number",
                    "required": False,
                },
            ],
        }

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        # Should reject due to duplicate name
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not unique" in str(response.json()).lower()


@pytest.mark.django_db
class TestExperimentFieldEdgeCases(BaseAPITestCase):
    """Test edge cases and complex scenarios for experiment fields."""

    def test_very_long_field_name(self) -> None:
        """Test that very long field names are handled correctly."""
        long_name = "A" * 500  # Very long name

        data = {
            "name": "Test Experiment",
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Submitter Email", "type": "text", "required": True},
                {"name": long_name, "type": "text", "required": False},
            ],
        }

        response = self.client.post(
            reverse("api:v1:experiments"),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()["data"]

        # Find field with long name (titlecased)
        long_field = next(
            (f for f in response_data["experiment_fields"] if len(f["name"]) > 400),  # noqa: PLR2004
            None,
        )
        assert long_field is not None

    def test_unicode_field_names_preserved(self) -> None:
        """Test that unicode characters in names are preserved and titlecased."""
        data = {
            "name": "Test Experiment",
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Submitter Email", "type": "text", "required": True},
                {"name": "温度 测量", "type": "number", "required": False},  # Chinese
                {
                    "name": "température eau",
                    "type": "number",
                    "required": False,
                },  # French
            ],
        }

        response = self.client.post(
            reverse("api:v1:experiments"),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()["data"]

        field_names = [f["name"] for f in response_data["experiment_fields"]]
        # Titlecase should be applied (though Chinese doesn't have case)
        assert "温度 测量" in field_names
        assert "Température Eau" in field_names

    def test_special_characters_in_field_names(self) -> None:
        """Test that special characters in names are handled."""
        data = {
            "name": "Test Experiment",
            "experiment_fields": [
                {"name": "Measurement Date", "type": "date", "required": True},
                {"name": "Submitter Email", "type": "text", "required": True},
                {"name": "pH (water)", "type": "number", "required": False},
                {"name": "Temperature [°C]", "type": "number", "required": False},
            ],
        }

        response = self.client.post(
            reverse("api:v1:experiments"),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()["data"]

        field_names = [f["name"] for f in response_data["experiment_fields"]]
        assert "Ph (Water)" in field_names
        assert "Temperature [°C]" in field_names

    def test_edit_name_with_name_only_field(self) -> None:
        """Test editing only name while keeping UUID, type, required, order."""
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
                "name": "Old Name",
                "type": FieldType.NUMBER.value,
                "required": False,
                "order": 2,
            },
        }

        experiment = ExperimentFactory.create(
            name="Test Experiment",
            experiment_fields=experiment_fields,
            created_by=self.user.email,
        )

        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Edit only the name
        data = {
            "experiment_fields": [
                {
                    "id": ph_uuid,
                    "name": "brand new name",
                    "type": "number",
                    "required": False,
                },
            ],
        }

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        # Verify name changed and titlecased
        field = next(
            (f for f in response_data["experiment_fields"] if f["id"] == ph_uuid), None
        )
        assert field is not None
        assert field["name"] == "Brand New Name"
        assert field["type"] == "number"
        assert field["required"] is False
        # Order is implicit - no order field in response

    def test_multiple_field_edits_in_single_request(self) -> None:
        """Test editing multiple fields' names and orders in one request."""
        uuid1 = Experiment.generate_field_uuid()
        uuid2 = Experiment.generate_field_uuid()
        uuid3 = Experiment.generate_field_uuid()

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
            uuid1: {
                "name": "Field A",
                "type": FieldType.TEXT.value,
                "required": False,
                "order": 2,
            },
            uuid2: {
                "name": "Field B",
                "type": FieldType.TEXT.value,
                "required": False,
                "order": 3,
            },
            uuid3: {
                "name": "Field C",
                "type": FieldType.TEXT.value,
                "required": False,
                "order": 4,
            },
        }

        experiment = ExperimentFactory.create(
            name="Test Experiment",
            experiment_fields=experiment_fields,
            created_by=self.user.email,
        )

        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Edit multiple fields (names and reorder by changing array positions)
        data = {
            "experiment_fields": [
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "name": "Measurement Date",
                    "type": "date",
                    "required": True,
                },
                {
                    "id": "00000000-0000-0000-0000-000000000002",
                    "name": "Submitter Email",
                    "type": "text",
                    "required": True,
                },
                {
                    "id": uuid2,
                    "name": "Renamed B",
                    "type": "text",
                    "required": False,
                },  # Position 2
                {
                    "id": uuid3,
                    "name": "Renamed C",
                    "type": "text",
                    "required": False,
                },  # Position 3
                {
                    "id": uuid1,
                    "name": "Renamed A",
                    "type": "text",
                    "required": False,
                },  # Position 4 (moved to end)
            ],
        }

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        # Verify all names changed and fields are in correct positions
        fields = response_data["experiment_fields"]
        assert fields[2]["id"] == uuid2
        assert fields[2]["name"] == "Renamed B"

        assert fields[3]["id"] == uuid3
        assert fields[3]["name"] == "Renamed C"

        assert fields[4]["id"] == uuid1
        assert fields[4]["name"] == "Renamed A"

    def test_add_and_edit_in_same_request(self) -> None:
        """Test adding new field and editing existing field in same request."""
        uuid1 = Experiment.generate_field_uuid()

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
            uuid1: {
                "name": "Existing Field",
                "type": FieldType.TEXT.value,
                "required": False,
                "order": 2,
            },
        }

        experiment = ExperimentFactory.create(
            name="Test Experiment",
            experiment_fields=experiment_fields,
            created_by=self.user.email,
        )

        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Edit existing field and add new field
        # Must include ALL existing fields
        data = {
            "experiment_fields": [
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "name": "Measurement Date",
                    "type": "date",
                    "required": True,
                },
                {
                    "id": "00000000-0000-0000-0000-000000000002",
                    "name": "Submitter Email",
                    "type": "text",
                    "required": True,
                },
                {
                    "name": "Brand New Field",
                    "type": "number",
                    "required": False,
                },  # Position 2 (new field)
                {
                    "id": uuid1,
                    "name": "Edited Field",
                    "type": "text",
                    "required": False,
                },  # Position 3 (edited name)
            ],
        }

        response = self.client.patch(
            reverse("api:v1:experiment-detail", kwargs={"id": experiment.id}),
            data=data,
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]

        # Should have 4 fields total
        assert len(response_data["experiment_fields"]) == 4  # noqa: PLR2004

        field_names = [f["name"] for f in response_data["experiment_fields"]]
        assert "Edited Field" in field_names
        assert "Brand New Field" in field_names
