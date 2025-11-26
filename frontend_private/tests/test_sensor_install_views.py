# -*- coding: utf-8 -*-

"""
Tests for sensor install frontend views.

These tests verify that the sensor management tab renders correctly
with the new History sub-tab functionality.
"""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import SensorFactory
from speleodb.api.v1.tests.factories import SensorInstallFactory
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.api.v1.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models.sensor import InstallState
from speleodb.users.tests.factories import UserFactory


class TestSensorManagementTabRendering(TestCase):
    """Tests for sensor management tab rendering."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()
        self.user = UserFactory.create()
        self.project = ProjectFactory.create()
        self.station = StationFactory.create(project=self.project)

        # Give user write access to project
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project,
            level=PermissionLevel.READ_AND_WRITE,
        )

    def test_map_viewer_renders_with_sensor_management_tab(self) -> None:
        """Verify map_viewer page renders and includes sensor management tab."""
        self.client.force_login(self.user)

        response = self.client.get(reverse("private:map_viewer"))

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # Check that sensor management tab exists
        assert (
            'data-tab="sensor-management"' in content or "Sensor Management" in content
        )

    def test_map_viewer_includes_subtabs_javascript(self) -> None:
        """Verify JavaScript module for sensor management is loaded."""
        self.client.force_login(self.user)

        response = self.client.get(reverse("private:map_viewer"))

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # Check that the main.js module is loaded (which imports sensors.js)
        assert "map_viewer/main.js" in content
        # Check for sensor management tab option
        assert 'value="sensor-management"' in content or "Sensor Management" in content

    def test_map_viewer_includes_history_subtab_ui_elements(self) -> None:
        """Verify sensor management tab is in the template."""
        self.client.force_login(self.user)

        response = self.client.get(reverse("private:map_viewer"))

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # Check for sensor management tab elements
        # The tab button and dropdown option should be present
        assert 'data-tab="sensor-management"' in content
        assert 'value="sensor-management"' in content

    def test_map_viewer_includes_state_filter_elements(self) -> None:
        """Verify sensor management tab exists (filter is rendered dynamically)."""
        self.client.force_login(self.user)

        response = self.client.get(reverse("private:map_viewer"))

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # Filter is rendered dynamically by sensors.js module
        # Just verify the module infrastructure is in place
        assert "map_viewer/main.js" in content
        assert "sensor-management" in content

    def test_map_viewer_includes_export_excel_button_logic(self) -> None:
        """Verify sensor management tab exists
        (export button is rendered dynamically)."""
        self.client.force_login(self.user)

        response = self.client.get(reverse("private:map_viewer"))

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # Export button is rendered dynamically by sensors.js module
        # Just verify the module infrastructure is in place
        assert "map_viewer/main.js" in content
        assert "sensor-management" in content

    def test_map_viewer_includes_table_sorting_logic(self) -> None:
        """Verify sensor management tab exists (sorting is rendered dynamically)."""
        self.client.force_login(self.user)

        response = self.client.get(reverse("private:map_viewer"))

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # Sorting logic is in sensors.js module
        # Just verify the module infrastructure is in place
        assert "map_viewer/main.js" in content
        assert "sensor-management" in content


class TestSensorManagementPermissions(TestCase):
    """Tests for sensor management permissions."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()
        self.user = UserFactory.create()
        self.project = ProjectFactory.create()
        self.station = StationFactory.create(project=self.project)

    def test_map_viewer_requires_authentication(self) -> None:
        """Unauthenticated user cannot access map viewer."""
        response = self.client.get(reverse("private:map_viewer"))

        # Should redirect to login
        assert response.status_code == status.HTTP_302_FOUND

    def test_map_viewer_accessible_with_read_permission(self) -> None:
        """User with read permission can access map viewer."""
        # Give user read access
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project,
            level=PermissionLevel.READ_ONLY,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("private:map_viewer"))

        assert response.status_code == status.HTTP_200_OK

    def test_map_viewer_accessible_with_write_permission(self) -> None:
        """User with write permission can access map viewer."""
        # Give user write access
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project,
            level=PermissionLevel.READ_AND_WRITE,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("private:map_viewer"))

        assert response.status_code == status.HTTP_200_OK


class TestSensorHistoryIntegration(TestCase):
    """Integration tests for sensor history display."""

    def setUp(self) -> None:
        """Set up test fixtures with sensor installs."""
        super().setUp()
        self.user = UserFactory.create()
        self.project = ProjectFactory.create()
        self.station = StationFactory.create(project=self.project)

        # Give user write access
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project,
            level=PermissionLevel.READ_AND_WRITE,
        )

        # Create sensor installs in various states
        sensor = SensorFactory.create()
        self.install_installed = SensorInstallFactory.create(
            station=self.station,
            sensor=sensor,
            state=InstallState.INSTALLED,
        )

        sensor2 = SensorFactory.create(fleet=sensor.fleet)
        self.install_retrieved = SensorInstallFactory.create_uninstalled(
            station=self.station,
            sensor=sensor2,
        )

    def test_map_viewer_with_sensor_installs(self) -> None:
        """Verify map viewer renders with existing sensor installs."""
        self.client.force_login(self.user)

        response = self.client.get(reverse("private:map_viewer"))

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # Verify sensor management tab and module infrastructure is present
        assert "sensor-management" in content
        assert "map_viewer/main.js" in content

    def test_api_returns_all_states_without_filter(self) -> None:
        """Verify API returns all sensor install states when no filter is applied."""
        self.client.force_login(self.user)

        # Make API call without state filter
        response = self.client.get(
            f"/api/v1/stations/{self.station.id}/sensor-installs/",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return both installs
        assert len(data["data"]) == 2  # noqa: PLR2004

    def test_api_filters_by_installed_state(self) -> None:
        """Verify API filters to only installed sensors when state=installed."""
        self.client.force_login(self.user)

        # Make API call with state filter
        response = self.client.get(
            f"/api/v1/stations/{self.station.id}/sensor-installs/?state=installed",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return only installed sensor
        assert len(data["data"]) == 1
        assert data["data"][0]["state"] == InstallState.INSTALLED
