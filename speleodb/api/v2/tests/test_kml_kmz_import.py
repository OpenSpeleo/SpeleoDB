"""Inspect and confirm KML/KMZ using the real parser, SQL and configured storage."""

from __future__ import annotations

import io
import zipfile
from decimal import Decimal
from typing import TYPE_CHECKING
from typing import Any

import orjson
import pytest
from allauth.account.models import EmailAddress
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from speleodb.api.v2.tests.database_constraints import unique_import_names
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISLayer
from speleodb.gis.models import GPSTrack
from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import LandmarkCollectionUserPermission
from speleodb.users.tests.factories import UserFactory
from speleodb.utils.s3_storages import GISLayerStorage
from speleodb.utils.s3_storages import GPSTrackStorage

if TYPE_CHECKING:
    from rest_framework.response import Response

    from speleodb.users.models import User


KML_OPEN: str = '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
KML_CLOSE: str = "</Document></kml>"
EXPECTED_SOURCE_PLACEMARKS: int = 5
EXPECTED_RENDERED_POINTS: int = 5
EXPECTED_RENDERED_LINES: int = 2
EXPECTED_DISTINCT_PLACES: int = 3
EXPECTED_MULTI_POINTS: int = 2
POINTS: str = (
    "<Placemark><name>First</name><Point>"
    "<coordinates>-87.50000004,20.10000004,12</coordinates></Point></Placemark>"
    "<Placemark><name>Duplicate</name><Point>"
    "<coordinates>-87.50000003,20.10000003,99</coordinates></Point></Placemark>"
    "<Placemark><name>Second</name><MultiGeometry>"
    "<Point><coordinates>-87.6,20.2</coordinates></Point>"
    "<Point><coordinates>-87.7,20.3</coordinates></Point>"
    "</MultiGeometry></Placemark>"
)
LINE: str = (
    "<Placemark><name>Path</name><LineString>"
    "<coordinates>-87.5,20.1 -87.6,20.2</coordinates>"
    "</LineString></Placemark>"
)
MIXED_GEOMETRY: str = (
    "<Placemark><name>Mixed feature</name><MultiGeometry>"
    "<Point><coordinates>-88,21</coordinates></Point>"
    "<LineString><coordinates>-88,21 -89,22</coordinates></LineString>"
    "</MultiGeometry></Placemark>"
)


def _source(content: str = POINTS, *, kmz: bool = False) -> SimpleUploadedFile:
    source: bytes = (KML_OPEN + content + KML_CLOSE).encode()
    if kmz:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("doc.kml", source)
        return SimpleUploadedFile("places.kmz", buffer.getvalue())
    return SimpleUploadedFile("places.kml", source)


@pytest.fixture
def import_user() -> User:
    user: User = UserFactory.create()
    EmailAddress.objects.create(
        user=user, email=user.email, primary=True, verified=True
    )
    return user


@pytest.fixture
def import_client(import_user: User) -> APIClient:
    token = Token.objects.create(user=import_user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


def _inspect(client: APIClient, source: SimpleUploadedFile) -> Response:
    return client.post(
        reverse("api:v2:kml-kmz-inspect"), {"file": source}, format="multipart"
    )


def _confirm(
    client: APIClient,
    source: SimpleUploadedFile,
    *,
    collection: LandmarkCollection | None = None,
) -> Response:
    data: dict[str, Any] = {"file": source}
    if collection is not None:
        data["collection"] = str(collection.id)
    return client.put(reverse("api:v2:kml-kmz-import"), data, format="multipart")


@pytest.mark.django_db
class TestKMLKMZImport:
    def test_inspection_reports_both_outcomes_without_rows_or_objects(
        self, import_client: APIClient, import_user: User
    ) -> None:
        gis_storage = GISLayerStorage()
        gps_storage = GPSTrackStorage()
        original_gis_objects = gis_storage.listdir("")
        original_gps_objects = gps_storage.listdir("")
        original_counts = (
            LandmarkCollection.objects.count(),
            LandmarkCollectionUserPermission.objects.count(),
            Landmark.objects.count(),
            GISLayer.objects.count(),
            GPSTrack.objects.count(),
        )

        response = _inspect(import_client, _source(POINTS + LINE + MIXED_GEOMETRY))

        assert response.status_code == status.HTTP_200_OK
        report = response.data
        assert report["source_placemarks"] == EXPECTED_SOURCE_PLACEMARKS
        assert report["places"] == {
            "eligible_placemarks": 3,
            "point_count": 4,
            "unique_coordinate_count": 3,
            "duplicate_coordinate_count": 1,
            "skipped_placemarks": 2,
        }
        assert report["overlay"]["source_placemarks"] == EXPECTED_SOURCE_PLACEMARKS
        assert report["overlay"]["line_parts"] == EXPECTED_RENDERED_LINES
        assert report["overlay"]["point_parts"] == EXPECTED_RENDERED_POINTS
        assert "-87.5" not in str(report)
        assert report["source_format"] == "KML"
        assert report["suggested_name"] == "places"
        assert not LandmarkCollection.objects.filter(
            personal_owner=import_user
        ).exists()
        assert original_counts == (
            LandmarkCollection.objects.count(),
            LandmarkCollectionUserPermission.objects.count(),
            Landmark.objects.count(),
            GISLayer.objects.count(),
            GPSTrack.objects.count(),
        )
        assert gis_storage.listdir("") == original_gis_objects
        assert gps_storage.listdir("") == original_gps_objects

    @pytest.mark.parametrize("kmz", [False, True])
    def test_confirmation_creates_places_only_and_reports_duplicates_and_bounds(
        self, import_client: APIClient, import_user: User, kmz: bool
    ) -> None:
        response = _confirm(
            import_client, _source(POINTS + LINE + MIXED_GEOMETRY, kmz=kmz)
        )

        assert response.status_code == status.HTTP_200_OK
        collection = LandmarkCollection.objects.get(personal_owner=import_user)
        assert response.data["landmarks_created"] == EXPECTED_DISTINCT_PLACES
        assert response.data["landmarks_skipped"] == 0
        assert response.data["duplicates_in_file"] == 1
        assert response.data["collection_id"] == str(collection.id)
        assert response.data["bounds"] == pytest.approx([-87.7, 20.1, -87.5, 20.3])
        assert not GISLayer.objects.filter(created_by=import_user.email).exists()
        assert not GPSTrack.objects.filter(created_by=import_user.email).exists()
        assert (
            collection.permissions.get(user=import_user).level == PermissionLevel.ADMIN
        )
        first = collection.landmarks.get(
            latitude=Decimal("20.1000000"), longitude=Decimal("-87.5000000")
        )
        assert first.name == "First"
        assert (
            collection.landmarks.filter(name="Second").count() == EXPECTED_MULTI_POINTS
        )
        assert not collection.landmarks.filter(name="Mixed feature").exists()

        repeat = _confirm(import_client, _source(POINTS, kmz=kmz))
        assert repeat.status_code == status.HTTP_200_OK
        assert repeat.data["landmarks_created"] == 0
        assert repeat.data["landmarks_skipped"] == EXPECTED_DISTINCT_PLACES
        assert repeat.data["duplicates_in_file"] == 1
        assert repeat.data["bounds"] is None
        assert collection.landmarks.count() == EXPECTED_DISTINCT_PLACES

    def test_valid_file_without_places_inspects_but_does_not_publish(
        self, import_client: APIClient, import_user: User
    ) -> None:
        response = _inspect(import_client, _source(LINE + MIXED_GEOMETRY))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["places"]["unique_coordinate_count"] == 0
        assert response.data["overlay"]["feature_count"] > 0
        confirm = _confirm(import_client, _source(LINE + MIXED_GEOMETRY))
        assert confirm.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert confirm.data["code"] == "KML_NO_ELIGIBLE_PLACES"
        assert not LandmarkCollection.objects.filter(
            personal_owner=import_user
        ).exists()
        assert not Landmark.objects.filter(created_by=import_user.email).exists()

    @pytest.mark.parametrize("inspect", [False, True])
    def test_invalid_file_and_missing_file_do_not_create_personal_collection(
        self, import_client: APIClient, import_user: User, inspect: bool
    ) -> None:
        method = import_client.post if inspect else import_client.put
        url = reverse("api:v2:kml-kmz-inspect" if inspect else "api:v2:kml-kmz-import")
        missing = method(url, {}, format="multipart")
        assert missing.status_code == status.HTTP_400_BAD_REQUEST
        malformed = method(
            url,
            {"file": SimpleUploadedFile("broken.kml", b"not XML")},
            format="multipart",
        )
        assert malformed.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert malformed.data["code"] == "XML_INVALID"
        assert not LandmarkCollection.objects.filter(
            personal_owner=import_user
        ).exists()

    # These non-atomic views must not inherit a test transaction that DRF's
    # authentication exception handler would mark for rollback.
    @pytest.mark.django_db(transaction=True)
    @pytest.mark.parametrize("inspect", [False, True])
    def test_rejects_multiple_files_and_unauthenticated_requests(
        self, import_client: APIClient, inspect: bool
    ) -> None:
        url = reverse("api:v2:kml-kmz-inspect" if inspect else "api:v2:kml-kmz-import")
        method = import_client.post if inspect else import_client.put
        response = method(url, {"file": [_source(), _source()]}, format="multipart")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        client = APIClient()
        unauthenticated = client.post if inspect else client.put
        response = unauthenticated(url, {"file": _source()}, format="multipart")
        assert response.status_code in {
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        }

    def test_permission_revoked_after_inspection_prevents_publication(
        self, import_client: APIClient, import_user: User
    ) -> None:
        collection = LandmarkCollection.objects.create(
            name="Shared", created_by=import_user.email
        )
        permission = LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=import_user,
            level=PermissionLevel.READ_AND_WRITE,
        )
        assert _inspect(import_client, _source()).status_code == status.HTTP_200_OK
        permission.level = PermissionLevel.READ_ONLY
        permission.save(update_fields=["level"])
        response = _confirm(import_client, _source(), collection=collection)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not collection.landmarks.exists()

    def test_long_unicode_names_and_one_fallback_timestamp(
        self, import_client: APIClient
    ) -> None:
        long_name = "洞" * 101
        content = (
            f"<Placemark><name>{long_name}</name><description>Cénote 洞</description>"
            "<Point><coordinates>1,2</coordinates></Point></Placemark>"
            "<Placemark><MultiGeometry>"
            "<Point><coordinates>2,3</coordinates></Point>"
            "<Point><coordinates>3,4</coordinates></Point>"
            "</MultiGeometry></Placemark>"
        )
        inspection = _inspect(import_client, _source(content))
        assert inspection.status_code == status.HTTP_200_OK
        assert any(warning["count"] > 0 for warning in inspection.data["warnings"])
        response = _confirm(import_client, _source(content))
        assert response.status_code == status.HTTP_200_OK
        collection = LandmarkCollection.objects.get(id=response.data["collection_id"])
        named = collection.landmarks.get(longitude=1)
        assert named.name == "洞" * 100
        assert named.description == "Cénote 洞"
        unnamed = list(collection.landmarks.exclude(id=named.id))
        assert len(unnamed) == EXPECTED_MULTI_POINTS
        assert unnamed[0].name == unnamed[1].name
        assert unnamed[0].name.startswith("Imported on ")

    @pytest.mark.parametrize("kmz", [False, True])
    def test_overlay_confirmation_creates_one_layer_preserving_original(
        self, import_client: APIClient, import_user: User, kmz: bool
    ) -> None:
        source = _source(POINTS + LINE + MIXED_GEOMETRY, kmz=kmz)
        original = source.read()
        source.seek(0)
        response = import_client.post(
            reverse("api:v2:gis-layers"),
            {"source_file": source, "name": "Whole source", "color": "#377eb8"},
            format="multipart",
        )
        assert response.status_code == status.HTTP_201_CREATED
        layer = GISLayer.objects.get(created_by=import_user.email)
        assert layer.source_f.name is not None
        assert layer.data_f.name is not None
        try:
            with layer.source_f.open("rb") as original_file:
                assert original_file.read() == original
            with layer.data_f.open("rb") as display_file:
                features = orjson.loads(display_file.read())["features"]
            assert {feature["geometry"]["type"] for feature in features} >= {
                "Point",
                "LineString",
            }
            assert not Landmark.objects.filter(created_by=import_user.email).exists()
            assert not LandmarkCollection.objects.filter(
                personal_owner=import_user
            ).exists()
            assert (
                layer.permissions.get(user=import_user).level == PermissionLevel.ADMIN
            )
        finally:
            layer.source_f.storage.delete(layer.source_f.name)
            layer.data_f.storage.delete(layer.data_f.name)

    @pytest.mark.django_db(transaction=True)
    def test_failed_confirmation_rolls_back_first_personal_collection(
        self, import_client: APIClient, import_user: User, settings: Any
    ) -> None:
        settings.DEBUG = False
        content = (
            "<Placemark><name>Same</name><Point>"
            "<coordinates>1,2</coordinates></Point></Placemark>"
            "<Placemark><name>Same</name><Point>"
            "<coordinates>2,3</coordinates></Point></Placemark>"
        )
        with unique_import_names(Landmark, created_by=import_user.email):
            response = _confirm(import_client, _source(content))
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert not Landmark.objects.filter(created_by=import_user.email).exists()
        assert not LandmarkCollection.objects.filter(
            personal_owner=import_user
        ).exists()
        assert not LandmarkCollectionUserPermission.objects.filter(
            user=import_user
        ).exists()
