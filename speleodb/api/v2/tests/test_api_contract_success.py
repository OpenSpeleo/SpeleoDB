"""Successful wire coverage for operations missing from earlier API scenarios."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import cast
from urllib.parse import urlencode

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.tests.factories import CylinderFactory
from speleodb.api.v2.tests.factories import CylinderFleetFactory
from speleodb.api.v2.tests.factories import CylinderFleetUserPermissionFactory
from speleodb.api.v2.tests.factories import CylinderInstallFactory
from speleodb.api.v2.tests.factories import CylinderPressureCheckFactory
from speleodb.api.v2.tests.factories import LandmarkCollectionFactory
from speleodb.api.v2.tests.factories import LandmarkCollectionUserPermissionFactory
from speleodb.api.v2.tests.factories import LandmarkFactory
from speleodb.api.v2.tests.factories import NoteStationResourceFactory
from speleodb.api.v2.tests.factories import SensorFactory
from speleodb.api.v2.tests.factories import SensorFleetFactory
from speleodb.api.v2.tests.factories import SensorFleetUserPermissionFactory
from speleodb.api.v2.tests.factories import SensorInstallFactory
from speleodb.api.v2.tests.factories import StationLogEntryFactory
from speleodb.api.v2.tests.factories import SubSurfaceStationFactory
from speleodb.api.v2.tests.factories import SurfaceMonitoringNetworkFactory
from speleodb.api.v2.tests.factories import (
    SurfaceMonitoringNetworkUserPermissionFactory,
)
from speleodb.api.v2.tests.factories import SurfaceStationFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Cylinder
from speleodb.gis.models import CylinderFleet
from speleodb.gis.models import CylinderInstall
from speleodb.gis.models import Sensor
from speleodb.gis.models import SensorFleet
from speleodb.testing.api_contract import assert_api_response
from speleodb.testing.gitlab_pool import get_pool
from speleodb.users.tests.factories import UserFactory


class TestSuccessfulContractVariants(BaseAPIProjectTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(PermissionLevel.ADMIN, PermissionType.USER)

    def update(self, route: str, kwargs: dict[str, Any], data: dict[str, Any]) -> Any:
        response = self.client.put(
            reverse("api:v2:" + route, kwargs=kwargs),
            data,
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.content
        assert_api_response(response)
        return response

    def test_form_nullable_clears_use_empty_values(self) -> None:
        fleet = cast("CylinderFleet", CylinderFleetFactory(created_by=self.user.email))
        CylinderFleetUserPermissionFactory(
            user=self.user, cylinder_fleet=fleet, level=PermissionLevel.ADMIN
        )
        cylinder = cast("Cylinder", CylinderFactory(fleet=fleet))
        install = cast(
            "CylinderInstall",
            CylinderInstallFactory(
                cylinder=cylinder, project=self.project, distance_from_entry=20
            ),
        )
        url = reverse(
            "api:v2:cylinder-install-detail", kwargs={"install_id": install.id}
        )
        for media in ("json", "multipart", "urlencoded"):
            install.distance_from_entry = 20
            install.save()
            options: dict[str, Any] = {"format": media}
            body: Any = {"distance_from_entry": None if media == "json" else ""}
            if media == "urlencoded":
                options = {"content_type": "application/x-www-form-urlencoded"}
                body = urlencode(body)
            response = self.client.patch(
                url, body, headers={"authorization": self.auth}, **options
            )
            assert response.status_code == status.HTTP_200_OK, response.content
            install.refresh_from_db()
            assert install.project == self.project
            assert install.distance_from_entry is None
            assert_api_response(response)
        response = self.client.patch(
            url, {"project": None}, format="json", headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        install.refresh_from_db()
        assert install.project == self.project
        assert_api_response(response)

    def test_initial_sensor_array_is_json_and_invalid_rows_do_not_create_fleet(
        self,
    ) -> None:
        url = reverse("api:v2:sensor-fleets")
        before = SensorFleet.objects.count()
        rejected = self.client.post(
            url,
            {"name": "Invalid nested fleet", "sensors": '{"name":"sensor"}'},
            format="multipart",
            headers={"authorization": self.auth},
        )
        assert rejected.status_code == status.HTTP_400_BAD_REQUEST
        assert SensorFleet.objects.count() == before
        assert_api_response(rejected)
        sensors_before = Sensor.objects.count()
        sensor_batches: tuple[list[dict[str, str]], ...] = (
            [{}],
            [{"name": "Valid row"}, {}],
        )
        for rows in sensor_batches:
            rejected = self.client.post(
                url,
                {"name": "Invalid nested fleet", "sensors": rows},
                format="json",
                headers={"authorization": self.auth},
            )
            assert rejected.status_code == status.HTTP_400_BAD_REQUEST
            errors = rejected.json()["errors"]
            invalid_index = str(len(rows) - 1)
            assert set(errors) == {invalid_index}
            assert set(errors[invalid_index]) == {"name"}
            assert errors[invalid_index]["name"]
            assert SensorFleet.objects.count() == before
            assert Sensor.objects.count() == sensors_before
            assert_api_response(rejected)
        accepted = self.client.post(
            url,
            {"name": "Initial sensors", "sensors": [{"name": "First sensor"}]},
            format="json",
            headers={"authorization": self.auth},
        )
        assert accepted.status_code == status.HTTP_201_CREATED, accepted.content
        fleet = SensorFleet.objects.get(id=accepted.json()["id"])
        assert fleet.sensors.get().created_by == self.user.email
        assert_api_response(accepted)

    def test_fleet_cylinder_install_and_sensor_put_variants(self) -> None:
        cylinder_fleet = cast(
            "CylinderFleet", CylinderFleetFactory(created_by=self.user.email)
        )
        CylinderFleetUserPermissionFactory(
            user=self.user,
            cylinder_fleet=cylinder_fleet,
            level=PermissionLevel.ADMIN,
        )
        cylinder = cast(
            "Cylinder",
            CylinderFactory(fleet=cylinder_fleet, created_by=self.user.email),
        )
        install = cast(
            "CylinderInstall",
            CylinderInstallFactory(
                cylinder=cylinder,
                project=self.project,
                created_by=self.user.email,
            ),
        )
        CylinderPressureCheckFactory(install=install, user="")
        self.update(
            "cylinder-fleet-detail",
            {"fleet_id": cylinder_fleet.id},
            {"name": "Updated fleet"},
        )
        self.update(
            "cylinder-detail",
            {"id": cylinder.id},
            {
                "name": "Updated cylinder",
                "o2_percentage": 21,
                "he_percentage": 0,
                "pressure": 3000,
                "unit_system": "imperial",
            },
        )
        self.update(
            "cylinder-install-detail",
            {"install_id": install.id},
            {
                "cylinder": str(cylinder.id),
                "location_name": "Updated location",
                "latitude": 20,
                "longitude": -87,
                "install_date": install.install_date.isoformat(),
                "install_user": self.user.email,
            },
        )
        sensor_fleet = cast(
            "SensorFleet", SensorFleetFactory(created_by=self.user.email)
        )
        SensorFleetUserPermissionFactory(
            user=self.user,
            sensor_fleet=sensor_fleet,
            level=PermissionLevel.ADMIN,
        )
        sensor = cast(
            "Sensor", SensorFactory(fleet=sensor_fleet, created_by=self.user.email)
        )
        SensorInstallFactory(sensor=sensor, station=SurfaceStationFactory())
        self.update(
            "sensor-fleet-detail",
            {"fleet_id": sensor_fleet.id},
            {"name": "Updated sensor fleet"},
        )
        self.update("sensor-detail", {"id": sensor.id}, {"name": "Updated sensor"})
        colleague = UserFactory()
        SensorFleetUserPermissionFactory(user=colleague, sensor_fleet=sensor_fleet)
        self.update(
            "sensor-fleet-permissions",
            {"fleet_id": sensor_fleet.id},
            {"user": colleague.email, "level": "READ_ONLY"},
        )
        exported = self.client.get(
            reverse(
                "api:v2:sensor-fleet-watchlist-export",
                kwargs={"fleet_id": sensor_fleet.id},
            ),
            {"days": 30},
            headers={"authorization": self.auth},
        )
        assert exported.status_code == status.HTTP_200_OK, exported.content
        assert_api_response(exported)

    def test_landmark_resource_log_and_network_updates(self) -> None:
        collection = LandmarkCollectionFactory(created_by=self.user.email)
        LandmarkCollectionUserPermissionFactory(
            user=self.user, collection=collection, level=PermissionLevel.ADMIN
        )
        landmark = LandmarkFactory(owner=self.user, collection=collection)
        self.update(
            "landmark-collection-detail",
            {"collection_id": collection.id},
            {"name": "Updated collection"},
        )
        self.update(
            "landmark-detail",
            {"id": landmark.id},
            {"name": "Updated landmark", "latitude": 20.5, "longitude": -87.5},
        )
        station = SubSurfaceStationFactory(
            project=self.project, created_by=self.user.email
        )
        resource = NoteStationResourceFactory(
            station=station, created_by=self.user.email
        )
        log = StationLogEntryFactory(station=station, created_by=self.user.email)
        self.update(
            "resource-detail",
            {"id": resource.id},
            {
                "title": "Updated note",
                "resource_type": "note",
                "text_content": "Updated text",
            },
        )
        self.update(
            "log-detail",
            {"id": log.id},
            {"title": "Updated log", "notes": "Updated notes"},
        )
        network = SurfaceMonitoringNetworkFactory(created_by=self.user.email)
        SurfaceMonitoringNetworkUserPermissionFactory(
            user=self.user, network=network, level=PermissionLevel.ADMIN
        )
        response = self.client.patch(
            reverse("api:v2:surface-network", kwargs={"network_id": network.id}),
            {"description": "Updated description"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.content
        assert_api_response(response)

    @pytest.mark.skip_if_lighttest
    def test_download_missing_source_at_valid_revision(self) -> None:
        get_pool().prepare(self.project)
        repo = self.project.git_repo
        self.addCleanup(repo.close)
        commit = repo.head.commit
        routes: list[tuple[str, dict[str, Any]]] = [
            (
                "project-download",
                {"id": self.project.id, "fileformat": "ariane_tml"},
            ),
            (
                "project-download-at-hash",
                {
                    "id": self.project.id,
                    "fileformat": "ariane_tml",
                    "hexsha": commit.hexsha,
                },
            ),
        ]
        for route, kwargs in routes:
            response = self.client.get(
                reverse("api:v2:" + route, kwargs=kwargs),
                headers={"authorization": self.auth},
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            assert "ariane.tml" in response.data["error"]
            assert commit.hexsha in response.data["error"]
            assert_api_response(response)

    @pytest.mark.skip_if_lighttest
    def test_project_revision_and_download_variants(self) -> None:
        get_pool().prepare(self.project)
        repo = self.project.git_repo
        self.addCleanup(repo.close)
        self.project.acquire_mutex(self.user)
        artifact = Path(__file__).parent / "artifacts" / "test_simple.tml"
        response = self.client.put(
            reverse(
                "api:v2:project-upload",
                kwargs={"id": self.project.id, "fileformat": "auto"},
            ),
            {
                "message": "Contract source",
                "artifact": SimpleUploadedFile(
                    "survey.tml",
                    artifact.read_bytes(),
                    content_type="application/octet-stream",
                ),
            },
            format="multipart",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.content
        commit = repo.head.commit
        blob = next(item for item in commit.tree.traverse() if item.type == "blob")
        routes: list[tuple[str, dict[str, Any]]] = [
            ("project-revisions", {"id": self.project.id}),
            ("project-gitexplorer", {"id": self.project.id, "hexsha": commit.hexsha}),
            (
                "project-download-at-hash",
                {"id": self.project.id, "fileformat": "dump", "hexsha": commit.hexsha},
            ),
            ("project-download-blob", {"id": self.project.id, "hexsha": blob.hexsha}),
        ]
        for route, kwargs in routes:
            response = self.client.get(
                reverse("api:v2:" + route, kwargs=kwargs),
                headers={"authorization": self.auth},
            )
            assert response.status_code == status.HTTP_200_OK, response.content
            assert_api_response(response)
