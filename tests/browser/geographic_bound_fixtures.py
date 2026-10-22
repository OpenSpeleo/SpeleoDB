"""Database-only records for the Geographic Bound dashboard UI."""

from __future__ import annotations

import secrets
from contextlib import contextmanager
from typing import TYPE_CHECKING

from django.urls import reverse

from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.geometry_services import create_gis_geometry
from speleodb.gis.models import GISGeometry
from speleodb.gis.models import GISProjectView
from speleodb.gis.models import GISView
from speleodb.surveys.models import Project
from speleodb.surveys.models import UserProjectPermission
from speleodb.users.tests.factories import VerifiedUserFactory

if TYPE_CHECKING:
    from collections.abc import Generator

    from speleodb.users.models import User


@contextmanager
def geographic_bound_records() -> Generator[dict[str, dict[str, str]]]:
    """Seed each dashboard independently; browser responses supply map inputs."""
    password: str = secrets.token_urlsafe(32)
    user: User = VerifiedUserFactory.create(
        email="viewer-bound-browser@example.test",
        name="Geographic Bound Browser",
        password=password,
    )
    records: dict[str, dict[str, str]] = {}
    for browser in ("chromium", "webkit"):
        polygon: GISGeometry = create_gis_geometry(
            GISGeometry(
                name=f"Browser bound {browser}",
                alias="入口",
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
        view: GISView = GISView.objects.create(
            owner=user,
            name=f"Browser bounded view {browser}",
            allow_precise_zoom=True,
            geographic_bound=polygon,
        )
        project: Project = ProjectFactory.create(
            name=f"Bound survey {browser}", created_by=user.email
        )
        UserProjectPermission.objects.create(
            project=project, target=user, level=PermissionLevel.ADMIN
        )
        GISProjectView.objects.create(gis_view=view, project=project, use_latest=True)
        records[browser] = {
            "email": user.email,
            "password": password,
            "view_id": str(view.id),
            "polygon_id": str(polygon.id),
            "polygon_name": polygon.name,
            "project_id": str(project.id),
            "project_name": project.name,
            "details_url": reverse(
                "private:gis_view_details", kwargs={"gis_view_id": view.id}
            ),
            "public_url": reverse("gis_view_map", kwargs={"gis_token": view.gis_token}),
            "public_data_url": reverse(
                "api:v2:gis-ogc:view-geojson", kwargs={"gis_token": view.gis_token}
            ),
        }
    yield records
