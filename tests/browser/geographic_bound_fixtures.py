"""Real GIS View records and stored surveys for browser clipping checks."""

from __future__ import annotations

import secrets
from contextlib import contextmanager
from typing import TYPE_CHECKING
from typing import Any

import orjson
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from speleodb.api.v2.tests.factories import ProjectCommitFactory
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.geometry_services import create_gis_geometry
from speleodb.gis.models import GISGeometry
from speleodb.gis.models import GISProjectView
from speleodb.gis.models import GISView
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.surveys.models import UserProjectPermission
from speleodb.users.tests.factories import VerifiedUserFactory

if TYPE_CHECKING:
    from collections.abc import Generator

    from speleodb.users.models import User


def survey_document(*, outside: bool) -> dict[str, Any]:
    """Crossing line and separate outside point make clipping observable."""
    return {
        "type": "FeatureCollection",
        "bbox": [-87.6, 20.0, -87.4, 20.2],
        "features": [
            {
                "type": "Feature",
                "properties": {"depth": 10, "section_name": "Crossing survey"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": (
                        [[-87.6, 20.15], [-87.59, 20.15]]
                        if outside
                        else [[-87.51, 20.105, -10], [-87.48, 20.105, -20]]
                    ),
                },
            },
            {
                "type": "Feature",
                "properties": {"depth": 1000, "name": "Outside entrance"},
                "geometry": {"type": "Point", "coordinates": [-87.6, 20.15]},
            },
        ],
    }


@contextmanager
def geographic_bound_records() -> Generator[dict[str, dict[str, str]]]:
    """Keep real surveys private to this fixture's independently logged-in owner."""
    password: str = secrets.token_urlsafe(32)
    user: User = VerifiedUserFactory.create(
        email="viewer-bound-browser@example.test",
        name="Geographic Bound Browser",
        password=password,
    )
    artifacts: list[ProjectGeoJSON] = []
    records: dict[str, dict[str, str]] = {}
    try:
        for browser in ("chromium", "webkit"):
            polygon: GISGeometry = create_gis_geometry(
                GISGeometry(
                    name=f"Browser bound {browser}",
                    alias="Boundary label",
                    color="#a855f7",
                    geojson={
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-87.5, 20.1],
                                [-87.49, 20.1],
                                [-87.49, 20.11],
                                [-87.5, 20.11],
                                [-87.5, 20.1],
                            ]
                        ],
                    },
                ),
                user,
            )
            line: GISGeometry = create_gis_geometry(
                GISGeometry(
                    name=f"Browser line {browser}",
                    geojson={
                        "type": "LineString",
                        "coordinates": [[-87.5, 20.1], [-87.49, 20.11]],
                    },
                ),
                user,
            )
            view: GISView = GISView.objects.create(
                owner=user,
                name=f"Browser bounded view {browser}",
                allow_precise_zoom=True,
                geographic_bound=polygon,
            )
            record: dict[str, str] = {
                "email": user.email,
                "password": password,
                "view_id": str(view.id),
                "polygon_id": str(polygon.id),
                "line_id": str(line.id),
                "details_url": reverse(
                    "private:gis_view_details", kwargs={"gis_view_id": view.id}
                ),
                "public_url": reverse(
                    "gis_view_map", kwargs={"gis_token": view.gis_token}
                ),
            }
            for outside in (False, True):
                kind: str = "outside" if outside else "crossing"
                project: Project = ProjectFactory.create(
                    name=f"Bound {kind} {browser}", created_by=user.email
                )
                UserProjectPermission.objects.create(
                    project=project, target=user, level=PermissionLevel.ADMIN
                )
                commit: ProjectCommit = ProjectCommitFactory.create(project=project)
                artifact: ProjectGeoJSON = ProjectGeoJSON.objects.create(
                    project=project,
                    commit=commit,
                    file=SimpleUploadedFile(
                        f"{kind}.geojson",
                        orjson.dumps(survey_document(outside=outside)),
                        content_type="application/geo+json",
                    ),
                )
                artifacts.append(artifact)
                GISProjectView.objects.create(
                    gis_view=view, project=project, use_latest=True
                )
                record[f"{kind}_id"] = str(project.id)
                record[f"{kind}_name"] = project.name
            records[browser] = record
        yield records
    finally:
        for artifact in artifacts:
            artifact.file.delete(save=False)
