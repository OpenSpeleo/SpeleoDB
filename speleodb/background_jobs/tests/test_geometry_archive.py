"""Database-backed GIS Geometry archive contents and permission snapshots."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from typing import Any
from zipfile import ZipFile

import orjson
import pytest

from speleodb.background_jobs.archive import build_archive
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISGeometry
from speleodb.gis.models import GISGeometryUserPermission

if TYPE_CHECKING:
    from pathlib import Path

    from speleodb.users.models import User


GEOMETRY_ARCHIVE_FORMAT_VERSION: int = 2
LINE: dict[str, Any] = {
    "type": "LineString",
    "coordinates": [[-87.123456789, 20.123456789], [-87.124567891, 20.124567891]],
}
POLYGON: dict[str, Any] = {
    "type": "Polygon",
    "coordinates": [
        [[-87.12, 20.12], [-87.13, 20.12], [-87.13, 20.13], [-87.12, 20.12]]
    ],
}


def _progress(stage: str, completed: int, total: int) -> None:
    pass


def _geometry(
    user: User,
    *,
    geojson: dict[str, Any] | None = None,
    level: PermissionLevel | None = PermissionLevel.READ_ONLY,
    permission_active: bool = True,
    active: bool = True,
) -> GISGeometry:
    geometry: GISGeometry = GISGeometry.objects.create(
        name="Precise geometry",
        created_by=user.email,
        color="#123456",
        geojson=LINE if geojson is None else geojson,
        revision=7,
        is_active=active,
    )
    if level is not None:
        GISGeometryUserPermission.objects.create(
            user=user,
            gis_geometry=geometry,
            level=level,
            is_active=permission_active,
        )
    return geometry


@pytest.mark.django_db
@pytest.mark.parametrize("geojson", [LINE, POLYGON], ids=["line", "polygon"])
def test_geometry_archive_preserves_geojson_and_metadata(
    user: User, tmp_path: Path, geojson: dict[str, Any]
) -> None:
    geometry: GISGeometry = _geometry(user, geojson=geojson)
    destination: Path = tmp_path / "export.zip"
    result = build_archive(user=user, destination=destination, progress=_progress)

    assert not result.partial
    assert result.manifest["format_version"] == GEOMETRY_ARCHIVE_FORMAT_VERSION
    assert result.manifest["selected_resources"] == 1
    assert result.manifest["exported_resources"] == 1
    record: dict[str, Any] = result.manifest["resources"][0]
    assert record["category"] == "geometries"
    assert record["id"] == str(geometry.id)
    assert record["name"] == geometry.name
    assert record["created_by"] == geometry.created_by
    assert record["color"] == geometry.color
    assert record["revision"] == geometry.revision
    assert record["creation_date"] == geometry.creation_date.isoformat()
    assert record["modified_date"] == geometry.modified_date.isoformat()
    assert record["outcome"] == "OK"
    assert len(record["files"]) == 1
    entry: dict[str, Any] = record["files"][0]
    assert entry["path"] == f"geometries/precise-geometry--{geometry.id}.geojson"
    with ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert b"- geometries/:" in archive.read("README.md")
        data: bytes = archive.read(entry["path"])
        assert orjson.loads(data) == geojson
        assert entry["sha256"] == hashlib.sha256(data).hexdigest()
        assert entry["size_bytes"] == len(data)
        assert orjson.loads(archive.read("manifest.json")) == result.manifest


@pytest.mark.django_db
def test_geometry_archive_requires_active_readable_permission(
    user: User, tmp_path: Path
) -> None:
    readable: list[GISGeometry] = [
        _geometry(user, level=level)
        for level in (
            PermissionLevel.READ_ONLY,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.ADMIN,
        )
    ]
    # Provenance does not authorize export, nor does a revoked grant or record.
    _geometry(user, level=None)
    _geometry(user, permission_active=False)
    _geometry(user, active=False)
    _geometry(user, level=PermissionLevel.WEB_VIEWER)
    result = build_archive(
        user=user, destination=tmp_path / "export.zip", progress=_progress
    )

    expected_ids: set[str] = {str(geometry.id) for geometry in readable}
    assert {record["id"] for record in result.manifest["resources"]} == expected_ids
    assert result.manifest["selected_resources"] == len(readable)
    assert result.manifest["exported_resources"] == len(readable)


@pytest.mark.django_db
def test_geometry_archive_retains_snapshotted_shape_after_edit_and_revocation(
    user: User, tmp_path: Path
) -> None:
    geometry: GISGeometry = _geometry(user)

    def edit_and_revoke(stage: str, completed: int, total: int) -> None:
        if stage == "Preparing archive":
            GISGeometry.objects.filter(pk=geometry.pk).update(
                geojson=POLYGON, revision=8, color="#abcdef", is_active=False
            )
            GISGeometryUserPermission.objects.filter(gis_geometry=geometry).update(
                is_active=False
            )

    destination: Path = tmp_path / "export.zip"
    result = build_archive(user=user, destination=destination, progress=edit_and_revoke)

    assert result.manifest["selected_resources"] == 1
    record: dict[str, Any] = result.manifest["resources"][0]
    assert record["revision"] == geometry.revision
    assert record["color"] == geometry.color
    with ZipFile(destination) as archive:
        assert orjson.loads(archive.read(record["files"][0]["path"])) == LINE

    fresh = build_archive(
        user=user, destination=tmp_path / "fresh.zip", progress=_progress
    )
    assert fresh.manifest["selected_resources"] == 0
    assert fresh.manifest["resources"] == []
