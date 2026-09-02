"""End-to-end API contract tests for collaborative GPS Tracks."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from typing import Any

import pytest
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.api.v2.tests.factories import GPSTrackFactory
from speleodb.api.v2.tests.factories import GPSTrackUserPermissionFactory
from speleodb.api.v2.tests.factories import TokenFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GPSTrackUserPermission
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.gis.models import GPSTrack
    from speleodb.users.models import User

SHARED_TRACK_COUNT = 8
PERMISSION_ROW_COUNT = 9


def _auth_for(user: User) -> str:
    return f"Token {TokenFactory.create(user=user).key}"


def _detail_url(track: GPSTrack) -> str:
    return reverse("api:v2:gps-track-detail", kwargs={"id": track.id})


def _permissions_url(track: GPSTrack) -> str:
    return reverse("api:v2:gps-track-permissions", kwargs={"id": track.id})


@pytest.mark.django_db
class TestGPSTrackAccessibleList(BaseAPITestCase):
    def test_list_contains_owned_and_shared_tracks_with_capabilities(self) -> None:
        created = GPSTrackFactory.create(creator=self.user, name="Created")
        shared = GPSTrackFactory.create(name="Shared")
        GPSTrackUserPermissionFactory.create(
            user=self.user,
            gps_track=shared,
            level=PermissionLevel.READ_AND_WRITE,
        )
        _ = GPSTrackFactory.create(name="Hidden")

        response = self.client.get(
            reverse("api:v2:gps-tracks"),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        tracks = {item["name"]: item for item in response.data}
        assert set(tracks) == {"Created", "Shared"}
        assert tracks["Created"] == {
            **tracks["Created"],
            "created_by": self.user.email,
            "user_permission_level": PermissionLevel.ADMIN,
            "user_permission_level_label": "ADMIN",
            "can_write": True,
            "can_delete": True,
        }
        assert tracks["Shared"]["created_by"] == shared.created_by
        assert tracks["Shared"]["user_permission_level_label"] == "READ_AND_WRITE"
        assert tracks["Shared"]["can_write"] is True
        assert tracks["Shared"]["can_delete"] is False
        assert tracks["Created"]["id"] == str(created.id)
        assert all(item["file"] for item in tracks.values())

    def test_list_excludes_revoked_permissions_and_inactive_tracks(self) -> None:
        revoked = GPSTrackFactory.create(name="Revoked")
        permission = GPSTrackUserPermissionFactory.create(
            user=self.user,
            gps_track=revoked,
            level=PermissionLevel.READ_ONLY,
        )
        permission.deactivate(deactivated_by=self.user)
        inactive = GPSTrackFactory.create(name="Inactive")
        GPSTrackUserPermissionFactory.create(
            user=self.user,
            gps_track=inactive,
            level=PermissionLevel.ADMIN,
        )
        inactive.deactivate(deactivated_by=self.user)

        response = self.client.get(
            reverse("api:v2:gps-tracks"),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_list_query_count_is_constant_as_tracks_grow(self) -> None:
        for index in range(SHARED_TRACK_COUNT):
            track = GPSTrackFactory.create(name=f"Shared {index}")
            GPSTrackUserPermissionFactory.create(
                user=self.user,
                gps_track=track,
                level=PermissionLevel.READ_ONLY,
            )
        self.client.force_authenticate(user=self.user)

        with self.assertNumQueries(1):
            response = self.client.get(reverse("api:v2:gps-tracks"))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == SHARED_TRACK_COUNT


@pytest.mark.django_db
class TestGPSTrackDetailPermissionMatrix(BaseAPITestCase):
    @parameterized.expand(
        [
            (PermissionLevel.READ_ONLY, "get", status.HTTP_200_OK),
            (PermissionLevel.READ_ONLY, "patch", status.HTTP_403_FORBIDDEN),
            (PermissionLevel.READ_ONLY, "put", status.HTTP_403_FORBIDDEN),
            (PermissionLevel.READ_ONLY, "delete", status.HTTP_403_FORBIDDEN),
            (PermissionLevel.READ_AND_WRITE, "get", status.HTTP_200_OK),
            (PermissionLevel.READ_AND_WRITE, "patch", status.HTTP_200_OK),
            (PermissionLevel.READ_AND_WRITE, "put", status.HTTP_200_OK),
            (PermissionLevel.READ_AND_WRITE, "delete", status.HTTP_403_FORBIDDEN),
            (PermissionLevel.ADMIN, "get", status.HTTP_200_OK),
            (PermissionLevel.ADMIN, "patch", status.HTTP_200_OK),
            (PermissionLevel.ADMIN, "put", status.HTTP_200_OK),
            (PermissionLevel.ADMIN, "delete", status.HTTP_200_OK),
        ],
    )
    def test_role_method_matrix(
        self,
        level: PermissionLevel,
        method: str,
        expected_status: int,
    ) -> None:
        track = GPSTrackFactory.create(name="Shared")
        collaborator = UserFactory.create()
        GPSTrackUserPermissionFactory.create(
            user=collaborator,
            gps_track=track,
            level=level,
        )
        payload: dict[str, str] | None = None
        if method == "patch":
            payload = {"name": "Patched"}
        elif method == "put":
            payload = {"name": "Put", "color": "#e41a1c"}

        client_method = getattr(self.client, method)
        request_kwargs: dict[str, Any] = {
            "headers": {"authorization": _auth_for(collaborator)}
        }
        if payload is not None:
            request_kwargs.update({"data": payload, "format": "json"})
        response = client_method(_detail_url(track), **request_kwargs)

        assert response.status_code == expected_status, response.data

    def test_soft_delete_is_atomic_and_preserves_file_and_prior_audit(self) -> None:
        track = GPSTrackFactory.create(creator=self.user)
        active_user = UserFactory.create()
        active = GPSTrackUserPermissionFactory.create(
            user=active_user,
            gps_track=track,
            level=PermissionLevel.READ_ONLY,
        )
        prior_revoker = UserFactory.create()
        revoked = GPSTrackUserPermissionFactory.create(
            gps_track=track,
            level=PermissionLevel.READ_ONLY,
        )
        revoked.deactivate(deactivated_by=prior_revoker)
        original_file_name = track.file.name

        response = self.client.delete(
            _detail_url(track),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        track.refresh_from_db()
        active.refresh_from_db()
        revoked.refresh_from_db()
        assert not track.is_active
        assert track.file.name == original_file_name
        assert not active.is_active
        assert active.deactivated_by == self.user
        assert not revoked.is_active
        assert revoked.deactivated_by == prior_revoker
        assert (
            self.client.get(
                _detail_url(track), headers={"authorization": self.auth}
            ).status_code
            == status.HTTP_404_NOT_FOUND
        )


@pytest.mark.django_db
class TestGPSTrackPermissionAPI(BaseAPITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.track = GPSTrackFactory.create(creator=self.user, name="Shared Track")
        self.target = UserFactory.create()
        self.url = _permissions_url(self.track)

    def _mutate(
        self,
        method: str,
        data: dict[str, str],
        *,
        auth: str | None = None,
    ) -> Any:
        return getattr(self.client, method)(
            self.url,
            data,
            format="json",
            headers={"authorization": auth or self.auth},
        )

    def test_reader_can_list_only_active_track_permissions_in_stable_order(
        self,
    ) -> None:
        reader = UserFactory.create()
        GPSTrackUserPermissionFactory.create(
            user=reader,
            gps_track=self.track,
            level=PermissionLevel.READ_ONLY,
        )
        writer = UserFactory.create(email="writer-a@example.com")
        GPSTrackUserPermissionFactory.create(
            user=writer,
            gps_track=self.track,
            level=PermissionLevel.READ_AND_WRITE,
        )
        revoked_user = UserFactory.create()
        revoked = GPSTrackUserPermissionFactory.create(
            user=revoked_user,
            gps_track=self.track,
        )
        revoked.deactivate(deactivated_by=self.user)
        other_track = GPSTrackFactory.create()
        _ = GPSTrackUserPermissionFactory.create(
            user=UserFactory.create(),
            gps_track=other_track,
        )

        response = self.client.get(
            self.url,
            headers={"authorization": _auth_for(reader)},
        )

        assert response.status_code == status.HTTP_200_OK
        assert [row["level"] for row in response.data] == [
            "ADMIN",
            "READ_AND_WRITE",
            "READ_ONLY",
        ]
        assert {row["user"] for row in response.data} == {
            self.user.email,
            writer.email,
            reader.email,
        }

    def test_permission_list_query_count_is_constant(self) -> None:
        for _ in range(8):
            GPSTrackUserPermissionFactory.create(
                gps_track=self.track,
                level=PermissionLevel.READ_ONLY,
            )
        self.client.force_authenticate(user=self.user)

        with self.assertNumQueries(3):
            response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == PERMISSION_ROW_COUNT

    @parameterized.expand(
        [
            (level, method)
            for level in [
                PermissionLevel.READ_ONLY,
                PermissionLevel.READ_AND_WRITE,
            ]
            for method in ["post", "put", "delete"]
        ]
    )
    def test_non_admin_cannot_mutate_permissions(
        self,
        level: PermissionLevel,
        method: str,
    ) -> None:
        caller = UserFactory.create()
        GPSTrackUserPermissionFactory.create(
            user=caller,
            gps_track=self.track,
            level=level,
        )
        payload = {"user": self.target.email}
        if method != "delete":
            payload["level"] = "READ_ONLY"

        response = self._mutate(method, payload, auth=_auth_for(caller))

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @parameterized.expand(["get", "post", "put", "delete"])
    def test_endpoint_requires_authentication(self, method: str) -> None:
        payload = {"user": self.target.email, "level": "READ_ONLY"}
        response = getattr(self.client, method)(self.url, payload, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_endpoint_rejects_malformed_token(self) -> None:
        response = self.client.get(
            self.url,
            headers={"authorization": "Token not-a-real-token"},
        )
        assert response.status_code in {
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        }

    def test_admin_grants_updates_revokes_and_reactivates_permission(self) -> None:
        created = self._mutate(
            "post",
            {"user": self.target.email, "level": "READ_ONLY"},
        )
        assert created.status_code == status.HTTP_201_CREATED
        permission = GPSTrackUserPermission.objects.get(
            user=self.target,
            gps_track=self.track,
        )
        assert permission.level == PermissionLevel.READ_ONLY

        duplicate = self._mutate(
            "post",
            {"user": self.target.email, "level": "ADMIN"},
        )
        assert duplicate.status_code == status.HTTP_400_BAD_REQUEST

        updated = self._mutate(
            "put",
            {"user": self.target.email, "level": "READ_AND_WRITE"},
        )
        assert updated.status_code == status.HTTP_200_OK
        permission.refresh_from_db()
        assert permission.level == PermissionLevel.READ_AND_WRITE

        revoked = self._mutate("delete", {"user": self.target.email})
        assert revoked.status_code == status.HTTP_200_OK
        permission.refresh_from_db()
        assert not permission.is_active
        assert permission.deactivated_by == self.user
        assert (
            self._mutate(
                "put",
                {"user": self.target.email, "level": "ADMIN"},
            ).status_code
            == status.HTTP_404_NOT_FOUND
        )
        assert (
            self._mutate("delete", {"user": self.target.email}).status_code
            == status.HTTP_404_NOT_FOUND
        )

        reactivated = self._mutate(
            "post",
            {"user": self.target.email, "level": "ADMIN"},
        )
        assert reactivated.status_code == status.HTTP_201_CREATED
        permission.refresh_from_db()
        assert permission.is_active
        assert permission.level == PermissionLevel.ADMIN
        assert permission.deactivated_by is None

    @parameterized.expand(
        [
            ({}, status.HTTP_400_BAD_REQUEST),
            (
                {"user": "unknown@example.com", "level": "READ_ONLY"},
                status.HTTP_404_NOT_FOUND,
            ),
            ({"user": 123, "level": "READ_ONLY"}, status.HTTP_400_BAD_REQUEST),
            ({"level": "READ_ONLY"}, status.HTTP_400_BAD_REQUEST),
            ({"user": "TARGET", "level": "INVALID"}, status.HTTP_400_BAD_REQUEST),
            ({"user": "TARGET", "level": "WEB_VIEWER"}, status.HTTP_400_BAD_REQUEST),
            ({"user": "TARGET"}, status.HTTP_400_BAD_REQUEST),
        ],
    )
    def test_grant_validation(
        self,
        payload: dict[str, Any],
        expected_status: int,
    ) -> None:
        resolved_payload = {
            key: self.target.email if value == "TARGET" else value
            for key, value in payload.items()
        }
        response = self.client.post(
            self.url,
            resolved_payload,
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == expected_status, response.data

    def test_grant_rejects_self_and_inactive_user(self) -> None:
        self_response = self._mutate(
            "post",
            {"user": self.user.email, "level": "READ_ONLY"},
        )
        assert self_response.status_code == status.HTTP_401_UNAUTHORIZED

        self.target.is_active = False
        self.target.save(update_fields=["is_active"])
        inactive_response = self._mutate(
            "post",
            {"user": self.target.email, "level": "READ_ONLY"},
        )
        assert inactive_response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unknown_and_inactive_tracks_are_not_exposed(self) -> None:
        unknown_url = reverse(
            "api:v2:gps-track-permissions",
            kwargs={"id": uuid.uuid4()},
        )
        assert (
            self.client.get(
                unknown_url,
                headers={"authorization": self.auth},
            ).status_code
            == status.HTTP_404_NOT_FOUND
        )

        self.track.deactivate(deactivated_by=self.user)
        assert (
            self.client.get(
                self.url,
                headers={"authorization": self.auth},
            ).status_code
            == status.HTTP_404_NOT_FOUND
        )
