"""The metadata migration preserves saved geometries and default landmarks."""

from __future__ import annotations

from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BASELINE = [("gis", "0042_project_geojson_generation")]
TARGET = [("gis", "0043_geometry_metadata_landmark_icon")]


@pytest.mark.django_db(transaction=True)
def test_metadata_migration_preserves_existing_rows() -> None:
    executor = MigrationExecutor(connection)
    latest: list[tuple[str, str]] = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate(BASELINE)
        apps = executor.loader.project_state(BASELINE).apps
        geometry_model: type[Any] = apps.get_model("gis", "GISGeometry")
        collection_model: type[Any] = apps.get_model("gis", "LandmarkCollection")
        landmark_model: type[Any] = apps.get_model("gis", "Landmark")
        geojson: dict[str, Any] = {
            "type": "LineString",
            "coordinates": [[-87, 20], [-87.001, 20]],
        }
        geometry = geometry_model.objects.create(
            name="Original",
            geojson=geojson,
            created_by="migration@example.com",
            revision=7,
        )
        collection = collection_model.objects.create(
            name="Original collection",
            created_by="migration@example.com",
        )
        landmark = landmark_model.objects.create(
            name="Original landmark",
            collection=collection,
            created_by="migration@example.com",
            latitude=20,
            longitude=-87,
        )
        executor = MigrationExecutor(connection)
        executor.migrate(TARGET)
        apps = executor.loader.project_state(TARGET).apps
        updated_geometry = apps.get_model("gis", "GISGeometry").objects.get(
            pk=geometry.pk
        )
        updated_landmark = apps.get_model("gis", "Landmark").objects.get(pk=landmark.pk)
        assert updated_geometry.alias == ""
        assert updated_geometry.description == ""
        assert updated_geometry.revision == geometry.revision
        assert updated_geometry.geojson == geojson
        assert updated_landmark.icon == "DEFAULT"
        assert updated_landmark.collection_id == collection.id
    finally:
        MigrationExecutor(connection).migrate(latest)
