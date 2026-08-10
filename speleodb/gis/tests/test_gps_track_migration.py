"""Migration tests for GPS Track collaboration."""

from __future__ import annotations

from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

GIS_0037: list[tuple[str, str]] = [("gis", "0037_landmark_collections")]
GIS_0038: list[tuple[str, str]] = [("gis", "0038_gpstrack_sharing")]
ADMIN_PERMISSION_LEVEL = 3


@pytest.mark.django_db(transaction=True)
def test_gps_track_migration_backfills_owner_admin_permission() -> None:
    executor = MigrationExecutor(connection)
    latest_targets: list[tuple[str, str]] = executor.loader.graph.leaf_nodes()

    try:
        executor.migrate(GIS_0037)
        old_apps = executor.loader.project_state(GIS_0037).apps
        old_user_model: type[Any] = old_apps.get_model("users", "User")
        old_gps_track_model: type[Any] = old_apps.get_model("gis", "GPSTrack")
        owner = old_user_model.objects.create(
            email="gps-track-owner@example.com",
            name="GPS Track Owner",
        )
        gps_track = old_gps_track_model.objects.create(
            name="Legacy Track",
            file="legacy-track.json",
            sha256_hash="a" * 64,
            color="#377eb8",
            user_id=owner.id,
        )

        executor = MigrationExecutor(connection)
        executor.migrate(GIS_0038)
        new_apps = executor.loader.project_state(GIS_0038).apps
        new_gps_track_model: type[Any] = new_apps.get_model("gis", "GPSTrack")
        permission_model: type[Any] = new_apps.get_model(
            "gis",
            "GPSTrackUserPermission",
        )
        migrated_track = new_gps_track_model.objects.get(id=gps_track.id)
        permission = permission_model.objects.get(
            gps_track_id=gps_track.id,
            user_id=owner.id,
        )

        assert migrated_track.is_active
        assert migrated_track.name == "Legacy Track"
        assert migrated_track.file.name == "legacy-track.json"
        assert migrated_track.sha256_hash == "a" * 64
        assert migrated_track.color == "#377eb8"
        assert migrated_track.user_id == owner.id
        assert permission.level == ADMIN_PERMISSION_LEVEL
        assert permission.is_active
        assert permission.deactivated_by_id is None

        executor = MigrationExecutor(connection)
        executor.migrate(GIS_0037)
        restored_apps = executor.loader.project_state(GIS_0037).apps
        restored_gps_track_model: type[Any] = restored_apps.get_model(
            "gis",
            "GPSTrack",
        )
        restored_track = restored_gps_track_model.objects.get(id=gps_track.id)
        restored_field_names = {
            field.name
            for field in restored_gps_track_model._meta.fields  # noqa: SLF001
        }

        assert restored_track.id == gps_track.id
        assert restored_track.file.name == "legacy-track.json"
        assert restored_track.sha256_hash == "a" * 64
        assert "is_active" not in restored_field_names
        with pytest.raises(LookupError):
            restored_apps.get_model("gis", "GPSTrackUserPermission")
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(latest_targets)
