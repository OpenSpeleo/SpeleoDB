# -*- coding: utf-8 -*-

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import SurfaceMonitoringNetwork
from speleodb.gis.models import SurfaceMonitoringNetworkUserPermission
from speleodb.users.models import User

pytestmark = pytest.mark.django_db


class TestSurfaceMonitoringNetworkApi:
    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture
    def authenticated_client(self, api_client: APIClient, user: User) -> APIClient:
        api_client.force_authenticate(user=user)
        return api_client

    def test_list_networks(self, user: User, authenticated_client: APIClient) -> None:
        # Create networks
        network1 = SurfaceMonitoringNetwork.objects.create(
            name="Network 1", created_by=user.email
        )
        _ = SurfaceMonitoringNetwork.objects.create(
            name="Network 2", created_by="other@example.com"
        )

        # Grant permissions
        SurfaceMonitoringNetworkUserPermission.objects.create(
            user=user, network=network1, level=PermissionLevel.ADMIN
        )

        # User should only see network1
        response = authenticated_client.get("/api/v1/surface-networks/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 1
        assert response.data["data"][0]["id"] == str(network1.id)

    def test_create_network(self, user: User, authenticated_client: APIClient) -> None:
        data = {"name": "New Network", "description": "Test Description"}
        response = authenticated_client.post("/api/v1/surface-networks/", data)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["name"] == "New Network"
        assert response.data["data"]["created_by"] == user.email

        # Check permission created
        network_id = response.data["data"]["id"]
        perm = SurfaceMonitoringNetworkUserPermission.objects.get(
            user=user, network_id=network_id
        )
        assert perm.level == PermissionLevel.ADMIN

    def test_get_network_details(
        self, user: User, authenticated_client: APIClient
    ) -> None:
        network = SurfaceMonitoringNetwork.objects.create(
            name="Network 1", created_by=user.email
        )
        SurfaceMonitoringNetworkUserPermission.objects.create(
            user=user, network=network, level=PermissionLevel.READ_ONLY
        )

        response = authenticated_client.get(f"/api/v1/surface-networks/{network.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["id"] == str(network.id)

    def test_update_network(self, user: User, authenticated_client: APIClient) -> None:
        network = SurfaceMonitoringNetwork.objects.create(
            name="Network 1", created_by=user.email
        )
        SurfaceMonitoringNetworkUserPermission.objects.create(
            user=user, network=network, level=PermissionLevel.READ_AND_WRITE
        )

        data = {"name": "Updated Network", "description": "Updated Description"}
        response = authenticated_client.put(
            f"/api/v1/surface-networks/{network.id}/", data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["name"] == "Updated Network"

        network.refresh_from_db()
        assert network.name == "Updated Network"

    def test_delete_network(self, user: User, authenticated_client: APIClient) -> None:
        network = SurfaceMonitoringNetwork.objects.create(
            name="Network 1", created_by=user.email
        )
        SurfaceMonitoringNetworkUserPermission.objects.create(
            user=user, network=network, level=PermissionLevel.ADMIN
        )

        response = authenticated_client.delete(
            f"/api/v1/surface-networks/{network.id}/"
        )
        assert response.status_code == status.HTTP_200_OK

        network.refresh_from_db()
        assert not network.is_active


class TestSurfaceMonitoringNetworkPermissionsApi:
    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture
    def authenticated_client(self, api_client: APIClient, user: User) -> APIClient:
        api_client.force_authenticate(user=user)
        return api_client

    def test_list_permissions(
        self, user: User, authenticated_client: APIClient
    ) -> None:
        network = SurfaceMonitoringNetwork.objects.create(
            name="Network 1", created_by=user.email
        )
        SurfaceMonitoringNetworkUserPermission.objects.create(
            user=user, network=network, level=PermissionLevel.ADMIN
        )

        response = authenticated_client.get(
            f"/api/v1/surface-networks/{network.id}/permissions/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 1
        assert response.data["data"][0]["user_display_email"] == user.email

    def test_grant_permission(
        self, user: User, authenticated_client: APIClient
    ) -> None:
        other_user = User.objects.create(email="other@example.com")
        network = SurfaceMonitoringNetwork.objects.create(
            name="Network 1", created_by=user.email
        )
        SurfaceMonitoringNetworkUserPermission.objects.create(
            user=user, network=network, level=PermissionLevel.ADMIN
        )

        data = {"user": other_user.email, "level": "READ_ONLY"}
        response = authenticated_client.post(
            f"/api/v1/surface-networks/{network.id}/permissions/", data
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert SurfaceMonitoringNetworkUserPermission.objects.filter(
            user=other_user, network=network, level=PermissionLevel.READ_ONLY
        ).exists()

    def test_update_permission(
        self, user: User, authenticated_client: APIClient
    ) -> None:
        other_user = User.objects.create(email="other@example.com")
        network = SurfaceMonitoringNetwork.objects.create(
            name="Network 1", created_by=user.email
        )
        SurfaceMonitoringNetworkUserPermission.objects.create(
            user=user, network=network, level=PermissionLevel.ADMIN
        )
        SurfaceMonitoringNetworkUserPermission.objects.create(
            user=other_user, network=network, level=PermissionLevel.READ_ONLY
        )

        data = {"user": other_user.email, "level": "ADMIN"}
        response = authenticated_client.put(
            f"/api/v1/surface-networks/{network.id}/permissions/", data
        )

        assert response.status_code == status.HTTP_200_OK
        perm = SurfaceMonitoringNetworkUserPermission.objects.get(
            user=other_user, network=network
        )
        assert perm.level == PermissionLevel.ADMIN

    def test_delete_permission(
        self, user: User, authenticated_client: APIClient
    ) -> None:
        other_user = User.objects.create(email="other@example.com")
        network = SurfaceMonitoringNetwork.objects.create(
            name="Network 1", created_by=user.email
        )
        SurfaceMonitoringNetworkUserPermission.objects.create(
            user=user, network=network, level=PermissionLevel.ADMIN
        )
        SurfaceMonitoringNetworkUserPermission.objects.create(
            user=other_user, network=network, level=PermissionLevel.READ_ONLY
        )

        data = {"user": other_user.email}
        response = authenticated_client.delete(
            f"/api/v1/surface-networks/{network.id}/permissions/", data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        perm = SurfaceMonitoringNetworkUserPermission.objects.get(
            user=other_user, network=network
        )
        assert not perm.is_active
