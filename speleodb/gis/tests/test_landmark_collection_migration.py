"""Migration tests for Landmark Collections."""

from __future__ import annotations

from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

GIS_0036: list[tuple[str, str]] = [("gis", "0036_alter_gpstrack_color")]
GIS_0037: list[tuple[str, str]] = [("gis", "0037_landmark_collections")]


@pytest.mark.django_db(transaction=True)
def test_landmark_collection_migration_rollback_restores_landmark_user() -> None:
    """Rollback to 0036 must repopulate the old non-null Landmark.user FK."""
    executor = MigrationExecutor(connection)
    latest_targets: list[tuple[str, str]] = executor.loader.graph.leaf_nodes()

    try:
        executor.migrate(GIS_0036)
        old_apps = executor.loader.project_state(GIS_0036).apps
        old_user_model: type[Any] = old_apps.get_model("users", "User")
        old_landmark_model: type[Any] = old_apps.get_model("gis", "Landmark")
        user = old_user_model.objects.create(
            email="rollback@example.com",
            name="Rollback User",
        )
        landmark = old_landmark_model.objects.create(
            name="Rollback Landmark",
            latitude="45.0000000",
            longitude="-122.0000000",
            user_id=user.id,
        )

        executor = MigrationExecutor(connection)
        executor.migrate(GIS_0037)
        new_apps = executor.loader.project_state(GIS_0037).apps
        new_landmark_model: type[Any] = new_apps.get_model("gis", "Landmark")
        new_collection_model: type[Any] = new_apps.get_model(
            "gis",
            "LandmarkCollection",
        )
        new_landmark = new_landmark_model.objects.get(id=landmark.id)
        personal_collection = new_collection_model.objects.get(
            collection_type="PERSONAL",
            personal_owner_id=user.id,
        )

        assert new_landmark.created_by == user.email
        assert personal_collection.color == "#ffffff"
        assert new_landmark.collection_id == personal_collection.id
        field_names = {field.name for field in new_landmark_model._meta.fields}  # noqa: SLF001
        assert "user" not in field_names

        executor = MigrationExecutor(connection)
        executor.migrate(GIS_0036)
        restored_apps = executor.loader.project_state(GIS_0036).apps
        restored_landmark_model: type[Any] = restored_apps.get_model(
            "gis",
            "Landmark",
        )
        restored_landmark = restored_landmark_model.objects.get(id=landmark.id)

        assert restored_landmark.user_id == user.id
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(latest_targets)
