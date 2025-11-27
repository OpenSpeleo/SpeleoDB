# -*- coding: utf-8 -*-

"""
Tests for sensor fleet watchlist frontend view.

These tests verify that the watchlist page renders correctly
and handles query parameters properly.
"""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from speleodb.api.v1.tests.factories import SensorFactory
from speleodb.api.v1.tests.factories import SensorFleetFactory
from speleodb.api.v1.tests.factories import SensorFleetUserPermissionFactory
from speleodb.api.v1.tests.factories import SensorInstallFactory
from speleodb.api.v1.tests.factories import SubSurfaceStationFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models.sensor import InstallStatus
from speleodb.users.tests.factories import UserFactory


class TestSensorFleetWatchlistView(TestCase):
    """Tests for sensor fleet watchlist view rendering."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()
        self.user = UserFactory.create()
        self.fleet = SensorFleetFactory.create(created_by=self.user.email)

        # Give user read access to fleet
        SensorFleetUserPermissionFactory.create(
            user=self.user,
            sensor_fleet=self.fleet,
            level=PermissionLevel.READ_ONLY,
        )

    def test_watchlist_view_renders(self) -> None:
        """Verify watchlist page renders successfully."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "private:sensor_fleet_watchlist",
                kwargs={"fleet_id": self.fleet.id},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # Check that watchlist page elements are present
        assert "Sensors Watchlist" in content
        assert "Look ahead (days)" in content
        assert "Update Watchlist" in content

    def test_watchlist_view_with_default_days(self) -> None:
        """Verify default days parameter (60) is used when not specified."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "private:sensor_fleet_watchlist",
                kwargs={"fleet_id": self.fleet.id},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # Check that default value (60) is in the input
        assert 'value="60"' in content or 'value="60"' in content

    def test_watchlist_view_with_custom_days(self) -> None:
        """Verify custom days parameter is used from query string."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "private:sensor_fleet_watchlist",
                kwargs={"fleet_id": self.fleet.id},
            )
            + "?days=30"
        )

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # Check that custom value (30) is in the input
        assert 'value="30"' in content

    def test_watchlist_view_invalid_days_defaults_to_60(self) -> None:
        """Verify invalid days parameter defaults to 60."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "private:sensor_fleet_watchlist",
                kwargs={"fleet_id": self.fleet.id},
            )
            + "?days=invalid"
        )

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # Should default to 60
        assert 'value="60"' in content

    def test_watchlist_view_negative_days_defaults_to_60(self) -> None:
        """Verify negative days parameter defaults to 60."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "private:sensor_fleet_watchlist",
                kwargs={"fleet_id": self.fleet.id},
            )
            + "?days=-10"
        )

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # Should default to 60
        assert 'value="60"' in content

    def test_watchlist_view_shows_sensors_due(self) -> None:
        """Verify sensors due for retrieval are displayed."""
        today = timezone.localdate()

        # Create sensor with install expiring soon
        sensor = SensorFactory.create(fleet=self.fleet)
        station = SubSurfaceStationFactory.create()

        SensorInstallFactory.create(
            sensor=sensor,
            station=station,
            status=InstallStatus.INSTALLED,
            expiracy_memory_date=today + timedelta(days=30),
            created_by=self.user.email,
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "private:sensor_fleet_watchlist",
                kwargs={"fleet_id": self.fleet.id},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # Check that sensor name appears in the content
        assert sensor.name in content

    def test_watchlist_view_empty_state(self) -> None:
        """Verify empty state message when no sensors are due."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "private:sensor_fleet_watchlist",
                kwargs={"fleet_id": self.fleet.id},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # Check for empty state message
        assert "No sensors are due for retrieval" in content or "No sensors" in content

    def test_watchlist_view_no_permission_redirects(self) -> None:
        """Verify user without permission is redirected."""
        other_user = UserFactory.create()
        self.client.force_login(other_user)

        response = self.client.get(
            reverse(
                "private:sensor_fleet_watchlist",
                kwargs={"fleet_id": self.fleet.id},
            )
        )

        # Should redirect to sensor fleets listing
        assert response.status_code == status.HTTP_302_FOUND
        assert reverse("private:sensor_fleets") in response.url  # type: ignore[attr-defined]

    def test_watchlist_view_unauthenticated_redirects(self) -> None:
        """Verify unauthenticated user is redirected."""
        response = self.client.get(
            reverse(
                "private:sensor_fleet_watchlist",
                kwargs={"fleet_id": self.fleet.id},
            )
        )

        # Should redirect to login
        assert response.status_code == status.HTTP_302_FOUND

    def test_watchlist_view_context_includes_days(self) -> None:
        """Verify context includes days parameter."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "private:sensor_fleet_watchlist",
                kwargs={"fleet_id": self.fleet.id},
            )
            + "?days=45"
        )

        assert response.status_code == status.HTTP_200_OK
        # Context should include days
        assert response.context["days"] == 45  # noqa: PLR2004

    def test_watchlist_view_context_includes_sensors(self) -> None:
        """Verify context includes sensors list."""
        today = timezone.localdate()

        sensor = SensorFactory.create(fleet=self.fleet)
        station = SubSurfaceStationFactory.create()

        SensorInstallFactory.create(
            sensor=sensor,
            station=station,
            status=InstallStatus.INSTALLED,
            expiracy_memory_date=today + timedelta(days=30),
            created_by=self.user.email,
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "private:sensor_fleet_watchlist",
                kwargs={"fleet_id": self.fleet.id},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        # Context should include sensors
        assert "sensors" in response.context
        assert len(response.context["sensors"]) == 1
        assert response.context["sensors"][0].id == sensor.id

    def test_watchlist_view_context_includes_fleet(self) -> None:
        """Verify context includes sensor fleet."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "private:sensor_fleet_watchlist",
                kwargs={"fleet_id": self.fleet.id},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        # Context should include sensor_fleet
        assert "sensor_fleet" in response.context
        assert response.context["sensor_fleet"].id == self.fleet.id
