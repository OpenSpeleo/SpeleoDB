"""Tests for Landmark Collection API endpoints."""

from __future__ import annotations

import io
import zipfile
from decimal import Decimal
from typing import Any

import gpxpy
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.common.enums import PermissionLevel
from speleodb.gis.landmark_collections import PERSONAL_LANDMARK_COLLECTION_COLOR
from speleodb.gis.landmark_collections import get_or_create_personal_landmark_collection
from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import LandmarkCollectionUserPermission
from speleodb.users.models import User


def _streaming_bytes(response: Any) -> bytes:
    return b"".join(response.streaming_content)


@pytest.mark.django_db
class TestLandmarkCollectionAPI:
    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture
    def owner(self) -> User:
        return User.objects.create_user(email="owner@example.com", password="pass")  # noqa: S106

    @pytest.fixture
    def reader(self) -> User:
        return User.objects.create_user(email="reader@example.com", password="pass")  # noqa: S106

    @pytest.fixture
    def writer(self) -> User:
        return User.objects.create_user(email="writer@example.com", password="pass")  # noqa: S106

    @pytest.fixture
    def collection(self, owner: User) -> LandmarkCollection:
        collection = LandmarkCollection.objects.create(
            name="Benchmarks",
            description="Shared points",
            created_by=owner.email,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=owner,
            level=PermissionLevel.ADMIN,
        )
        return collection

    def test_create_collection_grants_admin(
        self, api_client: APIClient, owner: User
    ) -> None:
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            reverse("api:v2:landmark-collections"),
            {
                "name": "Survey Control",
                "description": "Entrances",
                "color": "#ABCDEF",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        collection = LandmarkCollection.objects.get(name="Survey Control")
        permission = LandmarkCollectionUserPermission.objects.get(
            collection=collection,
            user=owner,
        )
        assert permission.level == PermissionLevel.ADMIN
        assert "is_active" not in response.json()
        assert response.json()["gis_token"] == collection.gis_token
        assert response.json()["color"] == "#abcdef"
        assert (
            response.json()["collection_type"]
            == LandmarkCollection.CollectionType.SHARED
        )
        assert response.json()["personal_owner"] is None

    def test_create_collection_rejects_invalid_color(
        self, api_client: APIClient, owner: User
    ) -> None:
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            reverse("api:v2:landmark-collections"),
            {"name": "Survey Control", "color": "javascript:alert(1)"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "color" in response.json()["errors"]

    def test_create_collection_forces_active(
        self, api_client: APIClient, owner: User
    ) -> None:
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            reverse("api:v2:landmark-collections"),
            {"name": "Cannot Predelete", "is_active": False},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        collection = LandmarkCollection.objects.get(name="Cannot Predelete")
        assert collection.is_active
        assert "is_active" not in response.json()

    def test_list_only_active_accessible_collections_includes_personal_collection(
        self,
        api_client: APIClient,
        owner: User,
        reader: User,
        collection: LandmarkCollection,
    ) -> None:
        hidden = LandmarkCollection.objects.create(
            name="Hidden",
            created_by=owner.email,
        )
        inactive = LandmarkCollection.objects.create(
            name="Inactive",
            created_by=owner.email,
            is_active=False,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=reader,
            level=PermissionLevel.READ_ONLY,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=inactive,
            user=reader,
            level=PermissionLevel.READ_ONLY,
        )

        api_client.force_authenticate(user=reader)
        response = api_client.get(reverse("api:v2:landmark-collections"))

        assert response.status_code == status.HTTP_200_OK
        names = {item["name"] for item in response.json()}
        assert names == {collection.name, "Personal Landmarks"}
        assert all("is_active" not in item for item in response.json())
        personal = next(
            item
            for item in response.json()
            if item["collection_type"] == LandmarkCollection.CollectionType.PERSONAL
        )
        assert personal["is_personal"] is True
        assert personal["color"] == PERSONAL_LANDMARK_COLLECTION_COLOR
        assert personal["gis_token"]
        assert personal["user_permission_level"] == PermissionLevel.ADMIN
        assert hidden.name not in names

    def test_detail_does_not_expose_active_flag(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
    ) -> None:
        api_client.force_authenticate(user=owner)
        response = api_client.get(
            reverse(
                "api:v2:landmark-collection-detail",
                kwargs={"collection_id": collection.id},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        assert "is_active" not in response.json()

    def test_write_user_can_update_shared_collection_color(
        self,
        api_client: APIClient,
        writer: User,
        collection: LandmarkCollection,
    ) -> None:
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=writer,
            level=PermissionLevel.READ_AND_WRITE,
        )

        api_client.force_authenticate(user=writer)
        response = api_client.patch(
            reverse(
                "api:v2:landmark-collection-detail",
                kwargs={"collection_id": collection.id},
            ),
            {"color": "#ABCDEF"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        collection.refresh_from_db()
        assert collection.color == "#abcdef"
        assert response.json()["color"] == "#abcdef"
        assert "is_active" not in response.json()

        response = api_client.patch(
            reverse(
                "api:v2:landmark-collection-detail",
                kwargs={"collection_id": collection.id},
            ),
            {"is_active": False},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        collection.refresh_from_db()
        assert collection.is_active

    def test_read_user_cannot_update_shared_collection_color(
        self,
        api_client: APIClient,
        reader: User,
        collection: LandmarkCollection,
    ) -> None:
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=reader,
            level=PermissionLevel.READ_ONLY,
        )

        api_client.force_authenticate(user=reader)
        response = api_client.patch(
            reverse(
                "api:v2:landmark-collection-detail",
                kwargs={"collection_id": collection.id},
            ),
            {"color": "#abcdef"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_personal_collection_owner_can_update_color_only(
        self,
        api_client: APIClient,
        owner: User,
    ) -> None:
        personal_collection = get_or_create_personal_landmark_collection(user=owner)

        api_client.force_authenticate(user=owner)
        response = api_client.patch(
            reverse(
                "api:v2:landmark-collection-detail",
                kwargs={"collection_id": personal_collection.id},
            ),
            {"color": "#123ABC"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        personal_collection.refresh_from_db()
        assert personal_collection.color == "#123abc"
        assert response.json()["color"] == "#123abc"
        assert response.json()["gis_token"] == personal_collection.gis_token
        assert "is_active" not in response.json()

        response = api_client.patch(
            reverse(
                "api:v2:landmark-collection-detail",
                kwargs={"collection_id": personal_collection.id},
            ),
            {"name": "Renamed Personal"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        personal_collection.refresh_from_db()
        assert personal_collection.name == "Personal Landmarks"

    def test_permission_grant_update_revoke_reactivate(
        self,
        api_client: APIClient,
        owner: User,
        reader: User,
        collection: LandmarkCollection,
    ) -> None:
        api_client.force_authenticate(user=owner)
        url = reverse(
            "api:v2:landmark-collection-permissions",
            kwargs={"collection_id": collection.id},
        )

        response = api_client.post(
            url,
            {"user": reader.email, "level": "READ_ONLY"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert "is_active" not in response_data["collection"]
        assert "is_active" not in response_data["permission"]

        response = api_client.put(
            url,
            {"user": reader.email, "level": "READ_AND_WRITE"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "is_active" not in response.json()
        permission = LandmarkCollectionUserPermission.objects.get(
            collection=collection,
            user=reader,
        )
        assert permission.level == PermissionLevel.READ_AND_WRITE

        response = api_client.delete(url, {"user": reader.email}, format="json")
        assert response.status_code == status.HTTP_200_OK
        permission.refresh_from_db()
        assert not permission.is_active

        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        permission_emails = {item["user_display_email"] for item in response.json()}
        assert reader.email not in permission_emails
        assert all("is_active" not in item for item in response.json())

        response = api_client.put(
            url,
            {"user": reader.email, "level": "READ_AND_WRITE"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        permission.refresh_from_db()
        assert not permission.is_active

        response = api_client.post(
            url,
            {"user": reader.email, "level": "ADMIN"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert "is_active" not in response_data["collection"]
        assert "is_active" not in response_data["permission"]
        permission.refresh_from_db()
        assert permission.is_active
        assert permission.level == PermissionLevel.ADMIN

    def test_permission_list_matches_project_sorting(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
    ) -> None:
        admin_user = User.objects.create_user(email="z-admin@example.com")
        writer_user = User.objects.create_user(email="a-writer@example.com")
        reader_user = User.objects.create_user(email="m-reader@example.com")
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=reader_user,
            level=PermissionLevel.READ_ONLY,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=admin_user,
            level=PermissionLevel.ADMIN,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=writer_user,
            level=PermissionLevel.READ_AND_WRITE,
        )

        api_client.force_authenticate(user=owner)
        response = api_client.get(
            reverse(
                "api:v2:landmark-collection-permissions",
                kwargs={"collection_id": collection.id},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert all("is_active" not in item for item in response_data)
        levels = [item["level_label"] for item in response_data]
        emails = [item["user_display_email"] for item in response_data]
        assert levels == ["ADMIN", "ADMIN", "READ_AND_WRITE", "READ_ONLY"]
        assert emails.index(admin_user.email) < emails.index(writer_user.email)
        assert emails.index(writer_user.email) < emails.index(reader_user.email)

    @pytest.mark.parametrize(
        "method",
        ["get", "post", "put", "delete"],
    )
    def test_personal_collection_permissions_cannot_be_managed(
        self,
        api_client: APIClient,
        owner: User,
        reader: User,
        method: str,
    ) -> None:
        personal_collection = get_or_create_personal_landmark_collection(user=owner)
        api_client.force_authenticate(user=owner)
        url = reverse(
            "api:v2:landmark-collection-permissions",
            kwargs={"collection_id": personal_collection.id},
        )
        payload = {"user": reader.email, "level": "READ_ONLY"}
        if method == "delete":
            payload = {"user": reader.email}

        if method == "get":
            response = api_client.get(url)
        else:
            response = getattr(api_client, method)(url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Personal landmark collection permissions" in response.json()["error"]

    def test_personal_collection_cannot_be_deleted(
        self,
        api_client: APIClient,
        owner: User,
    ) -> None:
        personal_collection = get_or_create_personal_landmark_collection(user=owner)

        api_client.force_authenticate(user=owner)
        response = api_client.delete(
            reverse(
                "api:v2:landmark-collection-detail",
                kwargs={"collection_id": personal_collection.id},
            )
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        personal_collection.refresh_from_db()
        assert personal_collection.is_active

    @pytest.mark.parametrize(
        "url_name",
        [
            "api:v2:landmark-collection-detail",
            "api:v2:landmark-collection-permissions",
        ],
    )
    def test_inactive_collection_object_routes_404(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
        url_name: str,
    ) -> None:
        collection.is_active = False
        collection.save(update_fields=["is_active", "modified_date"])
        api_client.force_authenticate(user=owner)

        response = api_client.get(
            reverse(url_name, kwargs={"collection_id": collection.id})
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_soft_delete_deactivates_permissions_and_hides_landmarks(
        self,
        api_client: APIClient,
        owner: User,
        reader: User,
        collection: LandmarkCollection,
    ) -> None:
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=reader,
            level=PermissionLevel.READ_ONLY,
        )
        landmark = Landmark.objects.create(
            name="Entrance",
            latitude=45,
            longitude=-122,
            created_by=owner.email,
            collection=collection,
        )

        api_client.force_authenticate(user=owner)
        response = api_client.delete(
            reverse(
                "api:v2:landmark-collection-detail",
                kwargs={"collection_id": collection.id},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        collection.refresh_from_db()
        landmark.refresh_from_db()
        assert not collection.is_active
        assert landmark.collection_id == collection.id
        assert not LandmarkCollectionUserPermission.objects.filter(
            collection=collection,
            is_active=True,
        ).exists()

        response = api_client.get(reverse("api:v2:landmarks"))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["landmarks"] == []

        api_client.force_authenticate(user=reader)
        response = api_client.get(reverse("api:v2:landmarks"))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["landmarks"] == []

        response = api_client.get(
            reverse("api:v2:landmark-detail", kwargs={"id": landmark.id})
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_landmark_visibility_and_write_matrix(
        self,
        api_client: APIClient,
        owner: User,
        reader: User,
        writer: User,
        collection: LandmarkCollection,
    ) -> None:
        owner_personal_collection = get_or_create_personal_landmark_collection(
            user=owner
        )
        private_landmark = Landmark.objects.create(
            name="Private",
            latitude=40,
            longitude=-120,
            created_by=owner.email,
            collection=owner_personal_collection,
        )
        collection_landmark = Landmark.objects.create(
            name="Shared",
            latitude=41,
            longitude=-121,
            created_by=owner.email,
            collection=collection,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=reader,
            level=PermissionLevel.READ_ONLY,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=writer,
            level=PermissionLevel.READ_AND_WRITE,
        )

        api_client.force_authenticate(user=reader)
        response = api_client.get(reverse("api:v2:landmarks"))
        assert response.status_code == status.HTTP_200_OK
        names = {item["name"] for item in response.json()["landmarks"]}
        assert names == {"Shared"}

        response = api_client.patch(
            reverse("api:v2:landmark-detail", kwargs={"id": collection_landmark.id}),
            {"name": "Reader Edit"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        api_client.force_authenticate(user=writer)
        response = api_client.patch(
            reverse("api:v2:landmark-detail", kwargs={"id": collection_landmark.id}),
            {"name": "Writer Edit"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        collection_landmark.refresh_from_db()
        assert collection_landmark.name == "Writer Edit"

        response = api_client.patch(
            reverse("api:v2:landmark-detail", kwargs={"id": private_landmark.id}),
            {"name": "No Access"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_landmark_assignment_requires_write(
        self,
        api_client: APIClient,
        owner: User,
        reader: User,
        collection: LandmarkCollection,
    ) -> None:
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=reader,
            level=PermissionLevel.READ_ONLY,
        )

        api_client.force_authenticate(user=reader)
        response = api_client.post(
            reverse("api:v2:landmarks"),
            {
                "name": "Shared",
                "latitude": 45,
                "longitude": -122,
                "collection": str(collection.id),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "collection" in response.json()["errors"]

    def test_collection_landmark_can_share_personal_coordinates(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
    ) -> None:
        owner_personal_collection = get_or_create_personal_landmark_collection(
            user=owner
        )
        Landmark.objects.create(
            name="Personal",
            latitude=Decimal("45.1234567"),
            longitude=Decimal("-122.1234567"),
            created_by=owner.email,
            collection=owner_personal_collection,
        )

        api_client.force_authenticate(user=owner)
        response = api_client.post(
            reverse("api:v2:landmarks"),
            {
                "name": "Collection",
                "latitude": "45.1234567",
                "longitude": "-122.1234567",
                "collection": str(collection.id),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        landmark = Landmark.objects.get(name="Collection")
        assert landmark.created_by == owner.email
        assert landmark.collection == collection

    @pytest.mark.parametrize(
        ("url_name", "filename", "content", "expected_track_count"),
        [
            (
                "api:v2:gpx-import",
                "landmarks.gpx",
                b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="SpeleoDB" xmlns="http://www.topografix.com/GPX/1/1">
  <wpt lat="45.1234567" lon="-122.1234567">
    <name>Imported GPX</name>
  </wpt>
</gpx>
""",
                0,
            ),
            (
                "api:v2:kml-kmz-import",
                "landmarks.kml",
                b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Imported KML</name>
      <Point>
        <coordinates>-122.1234567,45.1234567,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
""",
                None,
            ),
        ],
    )
    def test_import_to_collection_can_share_personal_coordinates(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
        url_name: str,
        filename: str,
        content: bytes,
        expected_track_count: int | None,
    ) -> None:
        owner_personal_collection = get_or_create_personal_landmark_collection(
            user=owner
        )
        Landmark.objects.create(
            name="Personal",
            latitude=Decimal("45.1234567"),
            longitude=Decimal("-122.1234567"),
            created_by=owner.email,
            collection=owner_personal_collection,
        )

        api_client.force_authenticate(user=owner)
        response = api_client.put(
            reverse(url_name),
            {
                "file": SimpleUploadedFile(filename, content),
                "collection": str(collection.id),
            },
            format="multipart",
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["landmarks_created"] == 1
        if expected_track_count is not None:
            assert response_data["gps_tracks_created"] == expected_track_count
        assert Landmark.objects.filter(
            collection=owner_personal_collection,
            latitude=Decimal("45.1234567"),
            longitude=Decimal("-122.1234567"),
        ).exists()
        assert Landmark.objects.filter(
            collection=collection,
            created_by=owner.email,
            latitude=Decimal("45.1234567"),
            longitude=Decimal("-122.1234567"),
        ).exists()

    @pytest.mark.parametrize("url_name", ["api:v2:gpx-import", "api:v2:kml-kmz-import"])
    def test_import_collection_assignment_requires_write_before_parsing(
        self,
        api_client: APIClient,
        reader: User,
        collection: LandmarkCollection,
        url_name: str,
    ) -> None:
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=reader,
            level=PermissionLevel.READ_ONLY,
        )

        api_client.force_authenticate(user=reader)
        response = api_client.put(
            reverse(url_name),
            {"collection": str(collection.id)},
            format="multipart",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "WRITE access" in response.json()["error"]

    @pytest.mark.parametrize(
        ("url_name", "filename", "content"),
        [
            (
                "api:v2:gpx-import",
                "landmarks.gpx",
                b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="SpeleoDB" xmlns="http://www.topografix.com/GPX/1/1">
  <wpt lat="45.1234567" lon="-122.1234567"><name>First</name></wpt>
  <wpt lat="46.1234567" lon="-123.1234567"><name>Second</name></wpt>
</gpx>
""",
            ),
            (
                "api:v2:kml-kmz-import",
                "landmarks.kml",
                b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>First</name>
      <Point><coordinates>-122.1234567,45.1234567,0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Second</name>
      <Point><coordinates>-123.1234567,46.1234567,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
""",
            ),
        ],
    )
    def test_failed_import_rolls_back_created_landmarks(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
        monkeypatch: pytest.MonkeyPatch,
        settings: Any,
        url_name: str,
        filename: str,
        content: bytes,
    ) -> None:
        settings.DEBUG = False
        failure_call_number = 2
        call_count = 0
        original_get_or_create = Landmark.objects.get_or_create

        def flaky_get_or_create(*args: Any, **kwargs: Any) -> tuple[Landmark, bool]:
            nonlocal call_count
            call_count += 1
            result = original_get_or_create(*args, **kwargs)
            if call_count == failure_call_number:
                raise RuntimeError("simulated import failure")
            return result

        monkeypatch.setattr(Landmark.objects, "get_or_create", flaky_get_or_create)

        api_client.force_authenticate(user=owner)
        response = api_client.put(
            reverse(url_name),
            {
                "file": SimpleUploadedFile(filename, content),
                "collection": str(collection.id),
            },
            format="multipart",
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert call_count == failure_call_number
        assert not Landmark.objects.filter(collection=collection).exists()


@pytest.mark.django_db
class TestLandmarkCollectionLandmarkExports:
    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture
    def owner(self) -> User:
        return User.objects.create_user(email="owner@example.com", password="pass")  # noqa: S106

    @pytest.fixture
    def collection(self, owner: User) -> LandmarkCollection:
        collection = LandmarkCollection.objects.create(
            name='Benchmarks: "Main"',
            description="Shared points",
            created_by=owner.email,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=owner,
            level=PermissionLevel.ADMIN,
        )
        return collection

    def _create_collection_landmark(
        self,
        owner: User,
        collection: LandmarkCollection,
        name: str = "Main Entrance",
    ) -> Landmark:
        return Landmark.objects.create(
            name=name,
            description="Primary entrance",
            latitude=Decimal("45.1234567"),
            longitude=Decimal("-122.1234567"),
            created_by=owner.email,
            collection=collection,
        )

    @pytest.mark.parametrize(
        "level",
        [
            PermissionLevel.READ_ONLY,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.ADMIN,
        ],
    )
    @pytest.mark.parametrize(
        ("url_name", "expected_content_type", "extension"),
        [
            (
                "api:v2:landmark-collection-landmarks-export-excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".xlsx",
            ),
            (
                "api:v2:landmark-collection-landmarks-export-gpx",
                "application/gpx+xml",
                ".gpx",
            ),
        ],
    )
    def test_read_write_and_admin_users_can_export(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
        level: int,
        url_name: str,
        expected_content_type: str,
        extension: str,
    ) -> None:
        user = User.objects.create_user(email=f"user-{level}@example.com")
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=user,
            level=level,
        )
        self._create_collection_landmark(owner=owner, collection=collection)

        api_client.force_authenticate(user=user)
        response = api_client.get(
            reverse(url_name, kwargs={"collection_id": collection.id})
        )

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == expected_content_type
        disposition = response["Content-Disposition"]
        assert "attachment" in disposition
        assert extension in disposition

    @pytest.mark.parametrize(
        "url_name",
        [
            "api:v2:landmark-collection-landmarks-export-excel",
            "api:v2:landmark-collection-landmarks-export-gpx",
        ],
    )
    def test_export_requires_collection_permission(
        self,
        api_client: APIClient,
        collection: LandmarkCollection,
        url_name: str,
    ) -> None:
        user = User.objects.create_user(email="stranger@example.com")
        api_client.force_authenticate(user=user)

        response = api_client.get(
            reverse(url_name, kwargs={"collection_id": collection.id})
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize(
        "url_name",
        [
            "api:v2:landmark-collection-landmarks-export-excel",
            "api:v2:landmark-collection-landmarks-export-gpx",
        ],
    )
    def test_inactive_collection_cannot_be_exported(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
        url_name: str,
    ) -> None:
        collection.is_active = False
        collection.save(update_fields=["is_active", "modified_date"])
        api_client.force_authenticate(user=owner)

        response = api_client.get(
            reverse(url_name, kwargs={"collection_id": collection.id})
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_excel_export_contains_data_headers_and_values(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
    ) -> None:
        self._create_collection_landmark(owner=owner, collection=collection)
        other_collection = LandmarkCollection.objects.create(
            name="Other",
            created_by=owner.email,
        )
        Landmark.objects.create(
            name="Other Collection",
            latitude=Decimal("46.0000000"),
            longitude=Decimal("-123.0000000"),
            created_by=owner.email,
            collection=other_collection,
        )
        Landmark.objects.create(
            name="Private Landmark",
            latitude=Decimal("47.0000000"),
            longitude=Decimal("-124.0000000"),
            created_by=owner.email,
            collection=get_or_create_personal_landmark_collection(user=owner),
        )

        api_client.force_authenticate(user=owner)
        response = api_client.get(
            reverse(
                "api:v2:landmark-collection-landmarks-export-excel",
                kwargs={"collection_id": collection.id},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        content = _streaming_bytes(response)
        assert content[:4] == b"PK\x03\x04"

        with zipfile.ZipFile(io.BytesIO(content)) as workbook_zip:
            shared_strings = workbook_zip.read("xl/sharedStrings.xml").decode()

        for value in ["Name", "Longitude", "Latitude", "Created By"]:
            assert value in shared_strings
        assert "Go To" not in shared_strings
        assert "Main Entrance" in shared_strings
        assert "owner@example.com" in shared_strings
        assert "Other Collection" not in shared_strings
        assert "Private Landmark" not in shared_strings
        assert ".xlsx" in response["Content-Disposition"]

    def test_empty_excel_export_is_valid_workbook(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
    ) -> None:
        api_client.force_authenticate(user=owner)
        response = api_client.get(
            reverse(
                "api:v2:landmark-collection-landmarks-export-excel",
                kwargs={"collection_id": collection.id},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        content = _streaming_bytes(response)
        assert content[:4] == b"PK\x03\x04"
        with zipfile.ZipFile(io.BytesIO(content)) as workbook_zip:
            shared_strings = workbook_zip.read("xl/sharedStrings.xml").decode()
        assert "Name" in shared_strings

    def test_gpx_export_contains_collection_waypoints_only(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
    ) -> None:
        self._create_collection_landmark(owner=owner, collection=collection)
        other_collection = LandmarkCollection.objects.create(
            name="Other",
            created_by=owner.email,
        )
        Landmark.objects.create(
            name="Other Collection",
            latitude=Decimal("46.0000000"),
            longitude=Decimal("-123.0000000"),
            created_by=owner.email,
            collection=other_collection,
        )
        Landmark.objects.create(
            name="Private Landmark",
            latitude=Decimal("47.0000000"),
            longitude=Decimal("-124.0000000"),
            created_by=owner.email,
            collection=get_or_create_personal_landmark_collection(user=owner),
        )

        api_client.force_authenticate(user=owner)
        response = api_client.get(
            reverse(
                "api:v2:landmark-collection-landmarks-export-gpx",
                kwargs={"collection_id": collection.id},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/gpx+xml"
        assert ".gpx" in response["Content-Disposition"]

        raw_gpx = _streaming_bytes(response).decode()
        assert "goto=" not in raw_gpx
        assert "/private/map_viewer/" not in raw_gpx
        assert '<gpx xmlns="http://www.topografix.com/GPX/1/1"' in raw_gpx
        assert 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' in raw_gpx
        assert (
            'xsi:schemaLocation="http://www.topografix.com/GPX/1/1 '
            'http://www.topografix.com/GPX/1/1/gpx.xsd"'
        ) in raw_gpx
        assert 'version="1.1"' in raw_gpx
        assert 'creator="SpeleoDB"' in raw_gpx
        assert "gpx.py -- https://github.com/tkrajina/gpxpy" not in raw_gpx

        parsed = gpxpy.parse(raw_gpx)
        assert len(parsed.waypoints) == 1
        waypoint = parsed.waypoints[0]
        assert waypoint.name == "Main Entrance"
        assert waypoint.latitude == pytest.approx(45.1234567)
        assert waypoint.longitude == pytest.approx(-122.1234567)
        assert waypoint.description is not None
        assert "Primary entrance" in waypoint.description
        assert "Created by: owner@example.com" in waypoint.description

    def test_empty_gpx_export_is_valid_gpx(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
    ) -> None:
        api_client.force_authenticate(user=owner)
        response = api_client.get(
            reverse(
                "api:v2:landmark-collection-landmarks-export-gpx",
                kwargs={"collection_id": collection.id},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        parsed = gpxpy.parse(_streaming_bytes(response).decode())
        assert parsed.waypoints == []
