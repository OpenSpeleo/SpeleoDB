"""Live Polygon bounds constrain web display without changing raw data access."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any
from typing import cast
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.deletion import ProtectedError
from django.http import StreamingHttpResponse
from django.test import Client
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v2.tests.factories import ProjectCommitFactory
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.admin.view import GISViewAdminForm
from speleodb.gis.geometry_services import create_gis_geometry
from speleodb.gis.geometry_services import update_gis_geometry
from speleodb.gis.models import GISGeometry
from speleodb.gis.models import GISGeometryUserPermission
from speleodb.gis.models import GISProjectView
from speleodb.gis.models import GISView
from speleodb.gis.models import ProjectGeoJSON
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django import forms

    from speleodb.users.models import User

POLYGON: dict[str, Any] = {
    "type": "Polygon",
    "coordinates": [[[-87.5, 20.1], [-87.499, 20.1], [-87.499, 20.101], [-87.5, 20.1]]],
}
LINE: dict[str, Any] = {
    "type": "LineString",
    "coordinates": [[-87.5, 20.1], [-87.499, 20.1]],
}


def _geometry(owner: User, geojson: dict[str, Any] | None = None) -> GISGeometry:
    return create_gis_geometry(
        GISGeometry(
            name="Geographic boundary",
            alias="Boundary label",
            color="#a855f7",
            geojson=POLYGON if geojson is None else geojson,
        ),
        owner,
    )


def _view(owner: User, bound: GISGeometry | None = None) -> GISView:
    return GISView.objects.create(
        owner=owner,
        name="Bounded view",
        allow_precise_zoom=False,
        geographic_bound=bound,
    )


@pytest.mark.django_db
def test_default_null_read_access_and_revoked_current_selection() -> None:
    creator = UserFactory.create()
    owner = UserFactory.create()
    geometry = _geometry(creator)
    view = _view(owner)
    assert view.geographic_bound is None
    view.geographic_bound = geometry
    with pytest.raises(ValidationError, match="read access"):
        view.save()
    permission = GISGeometryUserPermission.objects.create(
        user=owner, gis_geometry=geometry, level=PermissionLevel.READ_ONLY
    )
    view.save()
    permission.deactivate(creator)
    view.name = "Still bounded after access revocation"
    view.save()
    view.refresh_from_db()
    assert view.geographic_bound_id == geometry.id
    view.geographic_bound = None
    view.save()
    view.geographic_bound = geometry
    with pytest.raises(ValidationError, match="read access"):
        view.save()


@pytest.mark.django_db
def test_in_use_bound_cannot_be_deactivated_or_hard_deleted() -> None:
    owner = UserFactory.create()
    geometry = _geometry(owner)
    first = _view(owner, geometry)
    second = _view(owner, geometry)
    with pytest.raises(ValidationError, match="used as a GIS View"):
        geometry.deactivate(owner)
    with pytest.raises(ProtectedError):
        geometry.delete()
    geometry.refresh_from_db()
    assert geometry.is_active
    assert geometry.permissions.get(user=owner).is_active
    first.geographic_bound = None
    first.save()
    with pytest.raises(ValidationError, match="used as a GIS View"):
        geometry.deactivate(owner)
    second.delete()
    geometry.deactivate(owner)
    with pytest.raises(ValidationError, match="active Polygon"):
        _view(owner, geometry)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("original", "replacement"), [(LINE, POLYGON), (POLYGON, LINE)]
)
def test_geometry_type_is_immutable_through_model_service_and_api(
    original: dict[str, Any], replacement: dict[str, Any]
) -> None:
    owner = UserFactory.create()
    geometry = _geometry(owner, original)
    geometry.geojson = replacement
    with pytest.raises(ValidationError, match="type cannot change"):
        geometry.save()
    with pytest.raises(ValidationError, match="type cannot change"):
        update_gis_geometry(
            geometry_id=geometry.id,
            actor=owner,
            expected_revision=1,
            updates={"geojson": replacement},
        )
    client = APIClient()
    client.force_authenticate(owner)
    response = client.patch(
        reverse("api:v2:gis-geometry-detail", kwargs={"id": geometry.id}),
        {"expected_revision": 1, "geojson": replacement},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    geometry.refresh_from_db()
    assert geometry.geojson == original
    assert geometry.revision == 1


@pytest.mark.django_db
def test_management_api_nullable_selection_and_public_live_contract() -> None:
    owner = UserFactory.create()
    geometry = _geometry(owner)
    client = APIClient()
    client.force_authenticate(owner)
    response = client.post(
        reverse("api:v2:gis-views"),
        {"name": "Public", "allow_precise_zoom": False, "projects": []},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["geographic_bound"] is None
    view = GISView.objects.get(pk=response.data["id"])
    detail_url = reverse("api:v2:gis-view-detail", kwargs={"id": view.id})
    selected = client.patch(
        detail_url, {"geographic_bound": str(geometry.id)}, format="json"
    )
    assert selected.status_code == status.HTTP_200_OK
    assert selected.data["geographic_bound"] == geometry.id
    geometry.permissions.get(user=owner).deactivate(owner)
    renamed = client.patch(detail_url, {"name": "Renamed"}, format="json")
    assert renamed.status_code == status.HTTP_200_OK
    assert renamed.data["geographic_bound"] == geometry.id
    repeated = client.patch(
        detail_url, {"geographic_bound": str(geometry.id)}, format="json"
    )
    assert repeated.status_code == status.HTTP_200_OK
    public = APIClient()
    public_url = reverse(
        "api:v2:gis-ogc:view-geojson", kwargs={"gis_token": view.gis_token}
    )
    response = public.get(public_url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["geographic_bound"] == {
        "id": str(geometry.id),
        "revision": 1,
        "geojson": POLYGON,
        "color": geometry.color,
        "alias": geometry.alias,
    }
    geometry.permissions.get(user=owner).reactivate(PermissionLevel.ADMIN)
    changed: dict[str, Any] = {
        "type": "Polygon",
        "coordinates": [
            [[-87.5, 20.1], [-87.498, 20.1], [-87.499, 20.101], [-87.5, 20.1]]
        ],
    }
    update_gis_geometry(
        geometry_id=geometry.id,
        actor=owner,
        expected_revision=1,
        updates={"geojson": changed},
    )
    assert public.get(public_url).data["geographic_bound"] == {
        "id": str(geometry.id),
        "revision": 2,
        "geojson": changed,
        "color": geometry.color,
        "alias": geometry.alias,
    }
    deleted = client.delete(
        reverse("api:v2:gis-geometry-detail", kwargs={"id": geometry.id})
    )
    assert deleted.status_code == status.HTTP_400_BAD_REQUEST
    cleared = client.patch(detail_url, {"geographic_bound": None}, format="json")
    assert cleared.status_code == status.HTTP_200_OK
    assert cleared.data["geographic_bound"] is None
    assert public.get(public_url).data["geographic_bound"] is None


@pytest.mark.django_db
def test_selection_rejects_unavailable_and_nonpolygon_geometries() -> None:
    owner = UserFactory.create()
    foreign = _geometry(UserFactory.create())
    inactive = _geometry(owner)
    inactive.deactivate(owner)
    line = _geometry(owner, LINE)
    client = APIClient()
    client.force_authenticate(owner)
    for geometry_id in [foreign.id, inactive.id, line.id, uuid4()]:
        response = client.post(
            reverse("api:v2:gis-views"),
            {
                "name": "Rejected",
                "allow_precise_zoom": False,
                "projects": [],
                "geographic_bound": str(geometry_id),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "geographic_bound" in response.data["errors"]
    assert not GISView.objects.exists()


@pytest.mark.django_db
def test_admin_polygon_choices_and_preserved_revoked_current_bound() -> None:
    owner = UserFactory.create()
    current = _geometry(owner)
    available = _geometry(owner)
    foreign = _geometry(UserFactory.create())
    _geometry(owner, LINE)
    view = _view(owner, current)
    current.permissions.get(user=owner).deactivate(owner)
    form = GISViewAdminForm(instance=view)
    field = cast("forms.ModelChoiceField[GISGeometry]", form.fields["geographic_bound"])
    assert field.queryset is not None
    assert set(field.queryset.values_list("id", flat=True)) == {
        current.id,
        available.id,
    }
    add = GISViewAdminForm()
    field = cast("forms.ModelChoiceField[GISGeometry]", add.fields["geographic_bound"])
    assert field.queryset is not None
    assert set(field.queryset.values_list("id", flat=True)) == {
        current.id,
        available.id,
        foreign.id,
    }


@pytest.mark.django_db
def test_admin_rejects_geometry_type_changes() -> None:
    owner = UserFactory.create(is_staff=True, is_superuser=True)
    geometry = _geometry(owner)
    client = Client()
    client.force_login(owner)
    response = client.post(
        reverse("admin:gis_gisgeometry_change", args=[geometry.id]),
        {
            "name": geometry.name,
            "color": geometry.color,
            "geojson": json.dumps(LINE),
            "expected_revision": 1,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    assert "geojson" in response.context["adminform"].form.errors
    geometry.refresh_from_db()
    assert geometry.geojson == POLYGON


@pytest.mark.django_db
@pytest.mark.parametrize("owner_has_access", [True, False])
def test_admin_can_create_a_bound_view_in_one_submission(
    owner_has_access: bool,
) -> None:
    administrator = UserFactory.create(is_staff=True, is_superuser=True)
    owner = UserFactory.create()
    geometry = _geometry(administrator)
    if owner_has_access:
        GISGeometryUserPermission.objects.create(
            user=owner, gis_geometry=geometry, level=PermissionLevel.READ_ONLY
        )
    client = Client()
    client.force_login(administrator)
    response = client.post(
        reverse("admin:gis_gisview_add"),
        {
            "name": "Created by admin",
            "owner": owner.pk,
            "geographic_bound": str(geometry.pk),
            "project_views-TOTAL_FORMS": 0,
            "project_views-INITIAL_FORMS": 0,
            "project_views-MIN_NUM_FORMS": 0,
            "project_views-MAX_NUM_FORMS": 1000,
        },
    )
    if owner_has_access:
        assert response.status_code == status.HTTP_302_FOUND
        assert GISView.objects.get().geographic_bound_id == geometry.pk
    else:
        assert response.status_code == status.HTTP_200_OK
        assert "geographic_bound" in response.context["adminform"].form.errors
        assert not GISView.objects.exists()


@pytest.mark.django_db
def test_public_raw_urls_private_data_and_ogc_remain_unbounded() -> None:
    owner = UserFactory.create()
    geometry = _geometry(owner)
    view = _view(owner, geometry)
    project = ProjectFactory.create()
    commit = ProjectCommitFactory.create(project=project)
    feature: dict[str, Any] = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [10.0, 10.0]},
        "properties": {"name": "Outside the geographic bound"},
    }
    artifact = ProjectGeoJSON.objects.create(
        project=project,
        commit=commit,
        file=SimpleUploadedFile(
            "geographic-bound.geojson",
            json.dumps({"type": "FeatureCollection", "features": [feature]}).encode(),
            content_type="application/geo+json",
        ),
    )
    GISProjectView.objects.create(gis_view=view, project=project, use_latest=True)
    try:
        client = APIClient()
        public = client.get(
            reverse("api:v2:gis-ogc:view-geojson", kwargs={"gis_token": view.gis_token})
        )
        assert public.status_code == status.HTTP_200_OK
        assert len(public.data["projects"]) == 1
        assert urlparse(public.data["projects"][0]["geojson_file"]).path.endswith(
            artifact.file.name
        )
        ogc = client.get(
            reverse(
                "api:v2:gis-ogc:view-collection-items",
                kwargs={
                    "gis_token": view.gis_token,
                    "collection_id": f"{commit.id}_points",
                },
            )
        )
        assert ogc.status_code == status.HTTP_200_OK
        assert isinstance(ogc, StreamingHttpResponse)
        ogc_data: dict[str, Any] = json.loads(b"".join(ogc.streaming_content))
        assert ogc_data["features"][0]["geometry"] == feature["geometry"]
        client.force_authenticate(owner)
        private = client.get(reverse("api:v2:gis-view-data", kwargs={"id": view.id}))
        assert private.status_code == status.HTTP_200_OK
        assert "geographic_bound" not in private.data
        assert urlparse(private.data["geojson_files"][0]["url"]).path.endswith(
            artifact.file.name
        )
    finally:
        artifact.delete()
