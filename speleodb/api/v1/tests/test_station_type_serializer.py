# -*- coding: utf-8 -*-
"""Tests for SubSurfaceStation type field serialization."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from speleodb.api.v1.serializers.station import StationGeoJSONSerializer
from speleodb.api.v1.serializers.station import SubSurfaceStationSerializer
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import SubSurfaceStationFactory
from speleodb.common.enums import SubSurfaceStationType

if TYPE_CHECKING:
    from speleodb.surveys.models import Project


@pytest.fixture
def project() -> Project:
    """Create a test project."""
    return ProjectFactory.create()


@pytest.mark.django_db
class TestSubSurfaceStationSerializerType:
    """Test cases for SubSurfaceStationSerializer type field handling."""

    def test_serializer_accepts_science_type_on_create(self) -> None:
        """Test that serializer accepts 'science' type during creation."""
        data = {
            "name": "Science Station",
            "description": "Test science station",
            "latitude": "45.1234567",
            "longitude": "-123.4567890",
            "type": "science",
        }
        serializer = SubSurfaceStationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_serializer_accepts_bone_type_on_create(self) -> None:
        """Test that serializer accepts 'bone' type during creation."""
        data = {
            "name": "Bone Station",
            "description": "Test bone station",
            "latitude": "45.1234567",
            "longitude": "-123.4567890",
            "type": "bone",
        }
        serializer = SubSurfaceStationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_serializer_accepts_artifact_type_on_create(self) -> None:
        """Test that serializer accepts 'artifact' type during creation."""
        data = {
            "name": "Artifact Station",
            "description": "Test artifact station",
            "latitude": "45.1234567",
            "longitude": "-123.4567890",
            "type": "artifact",
        }
        serializer = SubSurfaceStationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_serializer_accepts_biology_type_on_create(self) -> None:
        """Test that serializer accepts 'biology' type during creation."""
        data = {
            "name": "Biology Station",
            "description": "Test biology station",
            "latitude": "45.1234567",
            "longitude": "-123.4567890",
            "type": "biology",
        }
        serializer = SubSurfaceStationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_serializer_accepts_geology_type_on_create(self) -> None:
        """Test that serializer accepts 'geology' type during creation."""
        data = {
            "name": "Geology Station",
            "description": "Test geology station",
            "latitude": "45.1234567",
            "longitude": "-123.4567890",
            "type": "geology",
        }
        serializer = SubSurfaceStationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_serializer_rejects_invalid_type_on_create(self) -> None:
        """Test that serializer rejects invalid type during creation."""
        data = {
            "name": "Invalid Station",
            "description": "Test invalid station",
            "latitude": "45.1234567",
            "longitude": "-123.4567890",
            "type": "invalid_type",
        }
        serializer = SubSurfaceStationSerializer(data=data)
        assert not serializer.is_valid()
        assert "type" in serializer.errors

    def test_serializer_rejects_type_change_on_update(self, project: Project) -> None:
        """Test that serializer rejects type change during update."""
        # Create an existing station
        station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.SCIENCE
        )

        # Try to update the type
        data = {"type": "bone"}
        serializer = SubSurfaceStationSerializer(
            instance=station, data=data, partial=True
        )
        assert not serializer.is_valid()
        assert "type" in serializer.errors
        assert "cannot be changed" in str(serializer.errors["type"][0]).lower()

    def test_serializer_allows_other_updates_without_type(
        self, project: Project
    ) -> None:
        """Test that serializer allows updates to other fields without type."""
        station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.SCIENCE
        )

        # Update only name and description
        data = {"name": "Updated Name", "description": "Updated description"}
        serializer = SubSurfaceStationSerializer(
            instance=station, data=data, partial=True
        )
        assert serializer.is_valid(), serializer.errors

    def test_serializer_includes_type_in_representation(self, project: Project) -> None:
        """Test that serializer includes type in output."""
        station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.BONE
        )

        serializer = SubSurfaceStationSerializer(instance=station)
        data = serializer.data

        assert "type" in data
        assert data["type"] == "bone"

    def test_serializer_type_field_not_in_read_only(self) -> None:
        """Test that type field is not in read_only_fields (allows creation)."""
        read_only = SubSurfaceStationSerializer.Meta.read_only_fields
        assert "type" not in read_only

    def test_serializer_allows_same_type_on_update(self, project: Project) -> None:
        """Test that serializer allows same type value on update (no actual change)."""
        station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.SCIENCE
        )

        # Try to "update" with the same type - should succeed
        # because no actual change is happening
        data = {"type": "science"}
        serializer = SubSurfaceStationSerializer(
            instance=station, data=data, partial=True
        )
        assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
class TestStationGeoJSONSerializerType:
    """Test cases for StationGeoJSONSerializer type field handling."""

    def test_geojson_serializer_includes_type_for_science(
        self, project: Project
    ) -> None:
        """Test that GeoJSON serializer includes type for science stations."""
        station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.SCIENCE
        )

        serializer = StationGeoJSONSerializer(instance=station)
        data = serializer.data

        # GeoJSON Feature structure
        assert data["type"] == "Feature"
        assert "properties" in data
        assert data["properties"]["type"] == "science"
        assert data["properties"]["station_type"] == "subsurface"

    def test_geojson_serializer_includes_type_for_bone(self, project: Project) -> None:
        """Test that GeoJSON serializer includes type for bone stations."""
        station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.BONE
        )

        serializer = StationGeoJSONSerializer(instance=station)
        data = serializer.data

        assert data["properties"]["type"] == "bone"
        assert data["properties"]["station_type"] == "subsurface"

    def test_geojson_serializer_includes_type_for_artifact(
        self, project: Project
    ) -> None:
        """Test that GeoJSON serializer includes type for artifact stations."""
        station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.ARTIFACT
        )

        serializer = StationGeoJSONSerializer(instance=station)
        data = serializer.data

        assert data["properties"]["type"] == "artifact"
        assert data["properties"]["station_type"] == "subsurface"

    def test_geojson_serializer_includes_type_for_biology(
        self, project: Project
    ) -> None:
        """Test that GeoJSON serializer includes type for biology stations."""
        station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.BIOLOGY
        )

        serializer = StationGeoJSONSerializer(instance=station)
        data = serializer.data

        assert data["properties"]["type"] == "biology"
        assert data["properties"]["station_type"] == "subsurface"

    def test_geojson_serializer_includes_type_for_geology(
        self, project: Project
    ) -> None:
        """Test that GeoJSON serializer includes type for geology stations."""
        station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.GEOLOGY
        )

        serializer = StationGeoJSONSerializer(instance=station)
        data = serializer.data

        assert data["properties"]["type"] == "geology"
        assert data["properties"]["station_type"] == "subsurface"

    def test_geojson_serializer_geometry_correct(self, project: Project) -> None:
        """Test that GeoJSON serializer produces correct geometry."""
        station = SubSurfaceStationFactory.create(
            project=project,
            type=SubSurfaceStationType.SCIENCE,
            latitude=45.123456,
            longitude=-123.456789,
        )

        serializer = StationGeoJSONSerializer(instance=station)
        data = serializer.data

        assert data["geometry"]["type"] == "Point"
        # Coordinates are [longitude, latitude] in GeoJSON
        # Note: GeoJSON uses float() which may have precision differences due to
        #       rounding
        coords = data["geometry"]["coordinates"]
        assert abs(coords[0] - float(station.longitude)) < 1e-6  # noqa: PLR2004
        assert abs(coords[1] - float(station.latitude)) < 1e-6  # noqa: PLR2004

    def test_geojson_serializer_batch_includes_types(self, project: Project) -> None:
        """Test that GeoJSON serializer handles multiple stations with different
        types."""
        science = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.SCIENCE, name="Science"
        )
        biology = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.BIOLOGY, name="Biology"
        )
        bone = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.BONE, name="Bone"
        )
        artifact = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.ARTIFACT, name="Artifact"
        )
        geology = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.GEOLOGY, name="Geology"
        )

        stations = [science, biology, bone, artifact, geology]
        serializer = StationGeoJSONSerializer(instance=stations, many=True)
        data = serializer.data

        assert len(data) == len(stations)
        types = {item["properties"]["type"] for item in data}
        assert types == {"science", "biology", "bone", "artifact", "geology"}


@pytest.mark.django_db
class TestSubSurfaceStationSerializerTypeEdgeCases:
    """Edge case tests for type field serialization."""

    def test_serializer_rejects_null_type(self) -> None:
        """Test that serializer rejects null type."""
        data = {
            "name": "Null Type Station",
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.4567890",
            "type": None,
        }
        serializer = SubSurfaceStationSerializer(data=data)
        assert not serializer.is_valid()
        assert "type" in serializer.errors

    def test_serializer_rejects_empty_string_type(self) -> None:
        """Test that serializer rejects empty string type."""
        data = {
            "name": "Empty Type Station",
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.4567890",
            "type": "",
        }
        serializer = SubSurfaceStationSerializer(data=data)
        assert not serializer.is_valid()
        assert "type" in serializer.errors

    def test_serializer_type_case_sensitive(self) -> None:
        """Test that type field is case sensitive."""
        # Uppercase should fail
        data = {
            "name": "Uppercase Type Station",
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.4567890",
            "type": "SCIENCE",  # Should be lowercase
        }
        serializer = SubSurfaceStationSerializer(data=data)
        assert not serializer.is_valid()
        assert "type" in serializer.errors

    def test_serializer_type_whitespace_rejected(self) -> None:
        """Test that type with whitespace is rejected."""
        data = {
            "name": "Whitespace Type Station",
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.4567890",
            "type": " science ",  # With whitespace
        }
        serializer = SubSurfaceStationSerializer(data=data)
        assert not serializer.is_valid()
        assert "type" in serializer.errors

    def test_full_update_with_type_rejected(self, project: Project) -> None:
        """Test that full update (PUT) with type is rejected."""
        station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.SCIENCE
        )

        # Full update data
        data = {
            "name": "Updated Name",
            "description": "Updated description",
            "latitude": "45.1234567",
            "longitude": "-123.4567890",
            "type": "bone",  # Trying to change type
        }
        serializer = SubSurfaceStationSerializer(
            instance=station, data=data, partial=False
        )
        assert not serializer.is_valid()
        assert "type" in serializer.errors

    def test_type_required_on_create_without_type_field(self) -> None:
        """Test that type is required during creation."""
        data = {
            "name": "No Type Station",
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.4567890",
            # type is not provided
        }
        serializer = SubSurfaceStationSerializer(data=data)
        assert not serializer.is_valid()
        assert "type" in serializer.errors
