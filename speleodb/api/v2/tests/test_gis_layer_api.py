"""API coverage for the lightweight GIS Layer contract."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISLayer

if TYPE_CHECKING:
    from rest_framework.response import Response


class SignedInMemoryStorage(InMemoryStorage):
    def url(self, name: str | None, **kwargs: object) -> str:
        return super().url(name)


@pytest.fixture(autouse=True)
def _in_memory_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = SignedInMemoryStorage()
    monkeypatch.setattr(GISLayer._meta.get_field("source_f"), "storage", storage)  # noqa: SLF001
    monkeypatch.setattr(GISLayer._meta.get_field("data_f"), "storage", storage)  # noqa: SLF001


def _geojson() -> SimpleUploadedFile:
    return SimpleUploadedFile(
        "layer.geojson",
        b'{"type":"FeatureCollection","features":[]}',
        content_type="application/geo+json",
    )


def _kml() -> SimpleUploadedFile:
    return SimpleUploadedFile(
        "layer.kml",
        (
            b'<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark>'
            b"<Point><coordinates>1,2</coordinates></Point>"
            b"</Placemark></kml>"
        ),
        content_type="application/vnd.google-earth.kml+xml",
    )


@pytest.mark.django_db
class TestGISLayerAPI(BaseAPITestCase):
    def _create(self, source: SimpleUploadedFile) -> Response:
        return self.client.post(
            reverse("api:v2:gis-layers"),
            {"name": "Protected Areas", "color": "#377eb8", "source_file": source},
            format="multipart",
            headers={"authorization": self.auth},
        )

    def test_geojson_is_stored_once_and_rendered_directly(self) -> None:
        with patch("speleodb.api.v2.views.gis_layer.compile_gis_layer") as compiler:
            response = self._create(_geojson())

        assert response.status_code == status.HTTP_201_CREATED
        compiler.assert_not_called()
        layer = GISLayer.objects.get()
        assert layer.created_by == self.user.email
        assert layer.source_f.name == layer.data_f.name
        assert response.data["file"]
        assert response.data["source_format"] == "GEOJSON"
        permission = layer.permissions.get(user=self.user)
        assert permission.level == PermissionLevel.ADMIN

    def test_kml_is_converted_to_one_display_geojson(self) -> None:
        response = self._create(_kml())

        assert response.status_code == status.HTTP_201_CREATED
        layer = GISLayer.objects.get()
        assert layer.source_f.name is not None
        assert layer.data_f.name is not None
        assert layer.source_f.name.endswith("source_layer.kml")
        assert layer.data_f.name.endswith("data.geojson")
        assert layer.source_f.name != layer.data_f.name
        with layer.data_f.open("rb") as data_file:
            assert b'"FeatureCollection"' in data_file.read()

    def test_malformed_supported_format_returns_safe_upload_error(self) -> None:
        response = self._create(
            SimpleUploadedFile(
                "layer.topojson",
                b'{"type":"not-a-topology"}',
                content_type="application/topo+json",
            )
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.data["code"] == "TOPOJSON_INVALID"
        assert response.data["error"] == (
            "The uploaded file is not a TopoJSON topology."
        )
        assert not GISLayer.objects.exists()

    def test_unsupported_extension_is_rejected_before_storage(self) -> None:
        response = self._create(
            SimpleUploadedFile(
                "layer.gpkg",
                b"unsupported",
                content_type="application/geopackage+sqlite3",
            )
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "source_file" in response.data["errors"]
        assert not GISLayer.objects.exists()

    def test_list_uses_permissions_and_exposes_the_display_file(self) -> None:
        assert self._create(_geojson()).status_code == status.HTTP_201_CREATED
        response = self.client.get(
            reverse("api:v2:gis-layers"),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["created_by"] == self.user.email
        assert response.data[0]["user_permission_level"] == PermissionLevel.ADMIN
        assert response.data[0]["file"]

    def test_source_endpoint_redirects_to_original_file(self) -> None:
        assert self._create(_geojson()).status_code == status.HTTP_201_CREATED
        layer = GISLayer.objects.get()
        response = self.client.get(
            reverse("api:v2:gis-layer-source", kwargs={"id": layer.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_302_FOUND
