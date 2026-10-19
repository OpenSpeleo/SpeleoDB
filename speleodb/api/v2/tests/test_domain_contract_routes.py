"""Real domain lifecycles through the supported v2 API.

Each request traverses Django and the contract observer sees the original bytes.
Projects are database-only canonical pool rows, without extra GitLab remotes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import urlencode

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v2.tests.factories import SubSurfaceStationFactory
from speleodb.api.v2.tests.factories import TokenFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISLayer
from speleodb.gis.models import GPSTrack
from speleodb.gis.models import Landmark
from speleodb.gis.models import StationResource
from speleodb.gis.models.experiment import MandatoryFieldUuid
from speleodb.surveys.models import UserProjectPermission
from speleodb.testing.api_contract import assert_api_response
from speleodb.testing.api_contract import contract_schema
from speleodb.testing.gitlab_pool import canonical_project
from speleodb.testing.gitlab_pool import canonical_user
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from collections.abc import Generator

    from django.core.files.storage import Storage

    from speleodb.surveys.models import Project
    from speleodb.users.models import User


LINE = {
    "type": "LineString",
    "coordinates": [[-87.5, 20.1], [-87.499, 20.1]],
}
KML = (
    b'<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><name>Point</name>'
    b"<Point><coordinates>-87.5,20.1</coordinates></Point></Placemark></kml>"
)
GPX = (
    b'<gpx version="1.1" creator="contract" xmlns="http://www.topografix.com/GPX/1/1">'
    b'<trk><name>Contract track</name><trkseg><trkpt lat="20.1" lon="-87.5"/>'
    b'<trkpt lat="20.101" lon="-87.501"/></trkseg></trk></gpx>'
)


@dataclass
class DomainAPI:
    user: User
    project: Project
    client: APIClient
    stored_files: list[tuple[Storage, str]] = field(default_factory=list)

    def send(
        self,
        method: str,
        path: str,
        data: Any = None,
        *,
        expected: int = status.HTTP_200_OK,
        media: str = "json",
    ) -> Any:
        if media == "urlencoded":
            options = {"content_type": "application/x-www-form-urlencoded"}
            data = urlencode(data or {})
        else:
            options = {"format": media}
        response = getattr(self.client, method)(f"/api/v2/{path}", data, **options)
        assert response.status_code == expected, (
            method,
            path,
            getattr(response, "content", b"streaming response"),
        )
        assert_api_response(response)
        return response

    def request(self, method: str, path: str, data: Any = None, **kwargs: Any) -> Any:
        response = self.send(method, path, data, **kwargs)
        if not response.content:
            return None
        return response.json()

    def download(self, path: str) -> None:
        response = self.send("get", path)
        content = (
            b"".join(response.streaming_content)
            if response.streaming
            else response.content
        )
        assert content

    def permissions(self, path: str) -> None:
        other = UserFactory.create()
        self.request("get", path)
        self.request(
            "post", path, {"user": other.email, "level": "READ_ONLY"}, expected=201
        )
        self.request("put", path, {"user": other.email, "level": "READ_AND_WRITE"})
        self.request("delete", path, {"user": other.email})
        for method in ("post", "put", "delete"):
            self.send(
                method,
                path,
                {"user": self.user.email, "level": "READ_ONLY"},
                expected=status.HTTP_401_UNAUTHORIZED,
            )

    def station(self) -> Any:
        return SubSurfaceStationFactory.create(project=self.project, type="sensor")


@pytest.fixture
def domain_api(db: None) -> Generator[DomainAPI]:
    user = canonical_user("A")
    project = canonical_project()
    UserProjectPermission.objects.update_or_create(
        target=user,
        project=project,
        defaults={"level": PermissionLevel.ADMIN, "is_active": True},
    )
    token = TokenFactory.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    api = DomainAPI(user, project, client)
    yield api
    for storage, name in api.stored_files:
        storage.delete(name)


def test_geometry_lifecycle_and_revision(domain_api: DomainAPI) -> None:
    api = domain_api
    created = api.request(
        "post", "gis-geometries/", {"name": "Line", "geojson": LINE}, expected=201
    )
    detail = f"gis-geometries/{created['id']}/"
    api.request("get", "gis-geometries/")
    api.request("get", detail)
    api.send("patch", detail, {"name": "Missing revision"}, expected=400)
    updated = api.request("patch", detail, {"name": "Edited", "expected_revision": 1})
    assert updated["revision"] == 2  # noqa: PLR2004
    api.send("patch", detail, {"expected_revision": 1}, expected=409)
    api.permissions(detail + "permissions/")
    api.request("delete", detail)


@pytest.mark.skip_if_lighttest
def test_uploaded_layer_lifecycle(domain_api: DomainAPI) -> None:
    api = domain_api
    api.send(
        "post",
        "gis-layers/",
        {"name": "Missing source"},
        media="multipart",
        expected=400,
    )
    created = api.request(
        "post",
        "gis-layers/",
        {
            "name": "Layer",
            "source_file": SimpleUploadedFile(
                "layer.geojson", b'{"type":"FeatureCollection","features":[]}'
            ),
        },
        media="multipart",
        expected=201,
    )
    layer = GISLayer.objects.get(id=created["id"])
    for stored in (layer.source_f, layer.data_f):
        if stored.name:
            api.stored_files.append((stored.storage, stored.name))
    detail = f"gis-layers/{created['id']}/"
    api.request("get", "gis-layers/")
    api.request("get", detail)
    api.request("patch", detail, {"name": "Edited layer"})
    source = api.send("get", detail + "source/", expected=302)
    assert source["Location"]
    api.permissions(detail + "permissions/")
    api.request("delete", detail)


@pytest.mark.skip_if_lighttest
def test_track_import_export_and_permissions(domain_api: DomainAPI) -> None:
    api = domain_api
    api.send("put", "import/gpx/", {}, media="multipart", expected=400)
    imported = api.request(
        "put",
        "import/gpx/",
        {"file": SimpleUploadedFile("track.gpx", GPX)},
        media="multipart",
    )
    track_id = imported["gps_track_ids"][0]
    track = GPSTrack.objects.get(id=track_id)
    assert track.file.name is not None
    api.stored_files.append((track.file.storage, track.file.name))
    detail = f"gps_tracks/{track_id}/"
    api.request("get", "gps_tracks/")
    api.request("get", detail)
    api.request("put", detail, {"name": "Updated track"})
    api.request("patch", detail, {"color": "#ff0000"})
    api.download(detail + "export/gpx/")
    api.permissions(detail + "permissions/")
    api.request("delete", detail)


@pytest.mark.skip_if_lighttest
def test_kml_inspection_and_import(domain_api: DomainAPI) -> None:
    api = domain_api
    for method, path in (
        ("post", "import/kml_kmz/inspect/"),
        ("put", "import/kml_kmz/"),
    ):
        api.send(method, path, {}, media="multipart", expected=400)
        api.request(
            method,
            path,
            {"file": SimpleUploadedFile("point.kml", KML)},
            media="multipart",
        )


def test_landmark_collection_lifecycle(domain_api: DomainAPI) -> None:
    api = domain_api
    created = api.request(
        "post", "landmark-collections/", {"name": "Source"}, expected=201
    )
    target = api.request(
        "post", "landmark-collections/", {"name": "Target"}, expected=201
    )
    detail = f"landmark-collections/{created['id']}/"
    target_detail = f"landmark-collections/{target['id']}/"
    api.request("get", "landmark-collections/")
    api.request("get", detail)
    api.request("put", detail, {"name": "Renamed source"})
    api.request("patch", detail, {"color": "#ff0000"})
    api.send("patch", detail, {"created_by": api.user.email}, expected=400)
    api.permissions(detail + "permissions/")
    landmark = api.request(
        "post",
        "landmarks/",
        {
            "name": "Entrance",
            "latitude": "20.123456789",
            "longitude": "-8.75e1",
            "collection": created["id"],
        },
        expected=201,
    )["landmark"]
    assert landmark["latitude"] == 20.1234568  # noqa: PLR2004
    landmark_detail = f"landmarks/{landmark['id']}/"
    api.request("get", "landmarks/")
    api.request("get", "landmarks/geojson/")
    api.request("get", landmark_detail)
    api.request(
        "put",
        landmark_detail,
        {"name": "Revised entrance", "latitude": 20.1, "longitude": -87.5},
    )
    boolean_coordinates = api.request(
        "patch", landmark_detail, {"latitude": False, "longitude": True}
    )["landmark"]
    assert boolean_coordinates["latitude"] == 0
    assert boolean_coordinates["longitude"] == 1
    api.send(
        "patch",
        landmark_detail,
        {"latitude": True, "longitude": True},
        media="multipart",
        expected=status.HTTP_400_BAD_REQUEST,
    )
    separated_coordinates = api.request(
        "patch",
        landmark_detail,
        {"latitude": "2_0.123_456_78", "longitude": "-8_7.5_0"},
    )["landmark"]
    assert separated_coordinates["latitude"] == pytest.approx(20.1234568)
    assert separated_coordinates["longitude"] == pytest.approx(-87.5)
    api.request("patch", landmark_detail, {"description": "Survey access"})
    api.download(detail + "landmarks/export/excel/")
    api.download(detail + "landmarks/export/gpx/")
    api.request(
        "post",
        detail + "landmarks/transfer/",
        {"landmark_ids": [landmark["id"]], "target_collection": target["id"]},
    )
    assert str(Landmark.objects.get(id=landmark["id"]).collection_id) == target["id"]
    api.request(
        "post",
        target_detail + "landmarks/bulk_delete/",
        {"landmark_ids": [landmark["id"]]},
    )
    personal = api.request(
        "post",
        "landmarks/",
        {"name": "Personal", "latitude": 20, "longitude": -87},
        expected=201,
    )["landmark"]
    personal_detail = f"landmark-collections/{personal['collection']}/"
    api.request("put", personal_detail, {"color": "#00ff00"})
    api.request("patch", personal_detail, {"color": "#0000ff"})
    api.send("put", personal_detail, {"name": "Forbidden"}, expected=400)
    api.request("delete", f"landmarks/{personal['id']}/")
    api.request("delete", detail)


def test_station_lead_tag_resource_and_log_lifecycle(domain_api: DomainAPI) -> None:
    api = domain_api
    project = f"projects/{api.project.id}/"
    station_data = {
        "name": "Station",
        "latitude": 20.1,
        "longitude": -87.5,
        "type": "sensor",
    }
    station = api.request("post", project + "stations/", station_data, expected=201)
    detail = f"stations/{station['id']}/"
    for path in (
        project + "stations/",
        project + "stations/geojson/",
        "stations/subsurface/",
        "stations/subsurface/geojson/",
        detail,
    ):
        api.request("get", path)
    api.request("put", detail, station_data)
    api.request("patch", detail, {"description": "Updated"})
    lead = api.request(
        "post",
        project + "exploration-leads/",
        {"latitude": 20.101, "longitude": -87.501},
        expected=201,
    )
    lead_detail = f"exploration-leads/{lead['id']}/"
    for path in (
        project + "exploration-leads/",
        project + "exploration-leads/geojson/",
        "exploration-leads/geojson/",
        lead_detail,
    ):
        api.request("get", path)
    api.request("put", lead_detail, {"latitude": 20.102, "longitude": -87.502})
    api.request("patch", lead_detail, {"description": "Investigate"})
    api.request("delete", lead_detail)
    tag = api.request(
        "post", "station_tags/", {"name": "Tag", "color": "#ff0000"}, expected=201
    )
    tag_detail = f"station_tags/{tag['id']}/"
    for path in ("station_tags/", "station_tags/colors/", tag_detail):
        api.request("get", path)
    api.request("put", tag_detail, {"name": "Tag revised", "color": "#00ff00"})
    api.request("patch", tag_detail, {"color": "#0000ff"})
    api.request("post", detail + "tags/", {"tag_id": tag["id"]})
    api.request("get", detail + "tags/")
    api.request("delete", detail + "tags/")
    api.request("delete", tag_detail)
    for method in ("put", "patch", "delete"):
        api.send(
            method, f"station_tags/{uuid.uuid4()}/", {"name": "Unknown"}, expected=404
        )
    resource = api.request(
        "post",
        detail + "resources/",
        {"resource_type": "note", "title": "Note", "text_content": "Observation"},
        expected=201,
    )
    resource_detail = f"resources/{resource['id']}/"
    api.request("get", detail + "resources/")
    api.request("get", resource_detail)
    api.request(
        "put", resource_detail, {"resource_type": "note", "title": "Updated note"}
    )
    api.request("patch", resource_detail, {"text_content": "Updated observation"})
    api.request("delete", resource_detail)
    api.send(
        "post",
        detail + "resources/",
        {"resource_type": "note", "title": "Missing text"},
        expected=400,
    )
    api.send(
        "post",
        detail + "resources/",
        {"resource_type": "document", "title": "Missing file"},
        expected=400,
    )
    log = api.request("post", detail + "logs/", {"title": "Visit"}, expected=201)
    log_detail = f"logs/{log['id']}/"
    api.request("get", detail + "logs/")
    api.request("get", log_detail)
    api.request("put", log_detail, {"title": "Revised visit"})
    api.request("patch", log_detail, {"notes": "New reading"})
    api.request("delete", log_detail)
    api.request("delete", detail)


@pytest.mark.skip_if_lighttest
def test_document_creation_uses_real_uploaded_file(domain_api: DomainAPI) -> None:
    api = domain_api
    station = api.station()
    created = api.request(
        "post",
        f"stations/{station.id}/resources/",
        {
            "resource_type": "document",
            "title": "Document",
            "file": SimpleUploadedFile("note.txt", b"Survey observation"),
        },
        media="multipart",
        expected=201,
    )
    resource = StationResource.objects.get(id=created["id"])
    for stored in (resource.file, resource.miniature):
        if stored.name:
            api.stored_files.append((stored.storage, stored.name))
    with resource.file.open("rb") as source:
        assert source.read() == b"Survey observation"


def test_resource_file_schema_constrains_filename_instead_of_contents() -> None:
    media = contract_schema()["paths"]["/api/v2/stations/{id}/resources/"]["post"][
        "requestBody"
    ]["content"]["multipart/form-data"]["schema"]
    file_schema = next(
        branch["properties"]["file"]
        for branch in media["anyOf"]
        if "file" in branch["required"]
    )
    assert file_schema["format"] == "binary"
    assert "x-filename-pattern" in file_schema
    assert {"pattern", "minLength", "maxLength"}.isdisjoint(file_schema)


def test_surface_network_lifecycle(domain_api: DomainAPI) -> None:
    api = domain_api
    created = api.request(
        "post", "surface-networks/", {"name": "Network"}, expected=201
    )
    detail = f"surface-networks/{created['id']}/"
    api.request("get", "surface-networks/")
    api.request("get", detail)
    api.request("put", detail, {"name": "Updated network"})
    api.request("patch", detail, {"description": "Description"})
    api.permissions(detail + "permissions/")
    station = api.request(
        "post",
        detail + "stations/",
        {"name": "Surface", "latitude": 20, "longitude": -87},
        expected=201,
    )
    for path in (
        detail + "stations/",
        detail + "stations/geojson/",
        "stations/surface/",
        "stations/surface/geojson/",
    ):
        api.request("get", path)
    api.request("delete", f"stations/{station['id']}/")
    api.request("delete", detail)


def test_cylinder_fleet_install_and_pressure_lifecycle(domain_api: DomainAPI) -> None:
    api = domain_api
    fleet = api.request("post", "cylinder-fleets/", {"name": "Cylinders"}, expected=201)
    detail = f"cylinder-fleets/{fleet['id']}/"
    api.request("get", "cylinder-fleets/")
    api.request("get", detail)
    api.request("put", detail, {"name": "Updated cylinders"})
    api.request("patch", detail, {"description": "Fleet notes"})
    api.send("patch", detail, {"created_by": api.user.email}, expected=400)
    api.permissions(detail + "permissions/")
    cylinder_data = {
        "name": "Cylinder",
        "o2_percentage": 21,
        "he_percentage": 0,
        "pressure": 200,
        "unit_system": "metric",
    }
    cylinder = api.request("post", detail + "cylinders/", cylinder_data, expected=201)
    cylinder_detail = f"cylinders/{cylinder['id']}/"
    api.request("get", detail + "cylinders/")
    api.request("get", cylinder_detail)
    api.request("put", cylinder_detail, cylinder_data)
    api.request("patch", cylinder_detail, {"notes": "Serviced"})
    install_data = {
        "cylinder": cylinder["id"],
        "project": str(api.project.id),
        "latitude": 20.1,
        "longitude": -87.5,
        "install_date": "2026-01-01",
    }
    install = api.request("post", "cylinder-installs/", install_data, expected=201)
    install_detail = f"cylinder-installs/{install['id']}/"
    api.request("get", "cylinder-installs/")
    api.request("get", "cylinder-installs/geojson/")
    api.request("get", install_detail)
    api.request("put", install_detail, {**install_data, "install_user": api.user.email})
    api.request("patch", install_detail, {"notes": "Checked"})
    check_data = {"pressure": 180, "unit_system": "metric", "check_date": "2026-01-02"}
    check = api.request(
        "post", install_detail + "pressure-checks/", check_data, expected=201
    )
    check_detail = install_detail + f"pressure-checks/{check['id']}/"
    api.request("get", install_detail + "pressure-checks/")
    api.request("get", check_detail)
    api.request("put", check_detail, check_data)
    api.request("patch", check_detail, {"notes": "Stable"})
    api.download(detail + "cylinders/export/")
    api.request("get", detail + "cylinders/watchlist/?days=0")
    api.send("get", detail + "cylinders/watchlist/?days=-1", expected=400)
    api.download(detail + "cylinders/watchlist/export/?days=invalid")
    api.request("delete", check_detail)
    api.request("delete", install_detail)
    api.request("delete", cylinder_detail)
    api.request("delete", detail)


def test_sensor_fleet_install_lifecycle(domain_api: DomainAPI) -> None:
    api = domain_api
    fleet = api.request(
        "post", "sensor-fleets/", {"name": "Sensors", "sensors": []}, expected=201
    )
    detail = f"sensor-fleets/{fleet['id']}/"
    api.request("get", "sensor-fleets/")
    api.request("get", detail)
    api.request("put", detail, {"name": "Updated sensors"})
    api.request("patch", detail, {"description": "Fleet notes"})
    api.send("patch", detail, {"created_by": api.user.email}, expected=400)
    api.permissions(detail + "permissions/")
    sensor = api.request("post", detail + "sensors/", {"name": "Sensor"}, expected=201)
    sensor_detail = f"sensors/{sensor['id']}/"
    api.request("get", detail + "sensors/")
    api.request("get", sensor_detail)
    api.request("put", sensor_detail, {"name": "Updated sensor"})
    api.request("patch", sensor_detail, {"notes": "Calibrated"})
    api.request("patch", sensor_detail + "toggle-functional/")
    api.request("patch", sensor_detail + "toggle-functional/")
    station = api.station()
    installs = f"stations/{station.id}/sensor-installs/"
    install = api.request(
        "post",
        installs,
        {
            "sensor": sensor["id"],
            "install_date": "2026-01-01",
            "expiracy_memory_date": "2026-02-01",
            "expiracy_battery_date": "2026-02-01",
        },
        expected=201,
    )
    api.request("get", installs)
    api.request("get", installs + f"{install['id']}/")
    api.download(installs + "export/excel/")
    api.download(detail + "sensors/export/")
    api.request("get", detail + "sensors/watchlist/?days=0")
    api.send("get", detail + "sensors/watchlist/?days=invalid", expected=400)
    api.download(detail + "sensors/watchlist/export/?days=-1")
    api.request(
        "patch",
        installs + f"{install['id']}/",
        {
            "status": "retrieved",
            "uninstall_date": "2026-01-02",
            "uninstall_user": api.user.email,
        },
    )
    api.request("delete", sensor_detail)
    api.request("delete", detail)


def test_experiment_definitions_and_record_lifecycle(domain_api: DomainAPI) -> None:
    api = domain_api
    for fields in (
        None,
        {"temp_bad": {"name": "No order", "type": "text"}},
        [{"name": "No options", "type": "select"}],
    ):
        api.send(
            "post",
            "experiments/",
            {"name": "Invalid", "experiment_fields": fields},
            expected=400,
        )
    experiment = api.request(
        "post",
        "experiments/",
        {
            "name": "Experiment",
            "experiment_fields": [
                {
                    "name": "Choice",
                    "type": "select",
                    "options": ["a", "b"],
                    "required": "OFF",
                    "order": " +0_2.00 ",
                },
                {"name": "Flag", "type": "boolean", "required": "TrUe", "order": True},
                {"name": "Optional", "type": "text", "required": 0, "order": False},
            ],
        },
        expected=201,
    )
    fields_by_name = {field["name"]: field for field in experiment["experiment_fields"]}
    assert fields_by_name["Choice"]["required"] is False
    assert fields_by_name["Choice"]["order"] == 2  # noqa: PLR2004
    assert fields_by_name["Flag"]["required"] is True
    assert fields_by_name["Flag"]["order"] == 1
    assert fields_by_name["Optional"]["required"] is False
    assert fields_by_name["Optional"]["order"] == 0
    detail = f"experiments/{experiment['id']}/"
    api.request("get", "experiments/")
    api.request("get", detail)
    api.request("put", detail, {"name": "Revised experiment"})
    api.request("patch", detail, {"description": "Monitoring"})
    station = api.station()
    records = f"stations/{station.id}/experiment/{experiment['id']}/records/"
    api.send("post", records, expected=status.HTTP_400_BAD_REQUEST)
    data = {
        MandatoryFieldUuid.MEASUREMENT_DATE.value: "2026-01-01",
        fields_by_name["Flag"]["id"]: True,
    }
    record = api.request("post", records, data, expected=201)
    record_detail = f"experiment_records/{record['id']}/"
    api.request("get", records)
    api.send("put", record_detail, expected=status.HTTP_400_BAD_REQUEST)
    api.request("put", record_detail, data)
    api.request("patch", record_detail)
    api.request(
        "patch",
        record_detail,
        {MandatoryFieldUuid.MEASUREMENT_DATE.value: "2026-01-02"},
    )
    api.send(
        "patch",
        record_detail,
        {MandatoryFieldUuid.MEASUREMENT_DATE.value: {"nested": "invalid"}},
        expected=400,
    )
    api.download(detail + "export/excel/")
    api.request("delete", record_detail)
    api.request("delete", detail)


@pytest.mark.parametrize("media", ["multipart", "urlencoded"])
def test_experiment_record_form_creation_and_json_updates(
    domain_api: DomainAPI, media: str
) -> None:
    api = domain_api
    experiment = api.request(
        "post",
        "experiments/",
        {"name": "Form dates", "experiment_fields": []},
        expected=201,
    )
    station = api.station()
    path = f"stations/{station.id}/experiment/{experiment['id']}/records/"
    date_field = MandatoryFieldUuid.MEASUREMENT_DATE.value
    record = api.request(
        "post", path, {date_field: "2026-01-01"}, media=media, expected=201
    )
    assert record["data"][date_field] == ["2026-01-01"]
    assert record["data"][MandatoryFieldUuid.SUBMITTER_EMAIL.value] == [api.user.email]
    assert api.request("get", path)[0]["data"] == record["data"]
    detail = f"experiment_records/{record['id']}/"
    for method in ("put", "patch"):
        rejected = api.request(
            method,
            detail,
            {date_field: "2026-01-02"},
            expected=status.HTTP_400_BAD_REQUEST,
        )
        assert any("must be a string" in error for error in rejected["errors"]["data"])
    api.request("delete", detail)

    json_record = api.request("post", path, {date_field: "2026-01-01"}, expected=201)
    assert json_record["data"][date_field] == "2026-01-01"
    assert (
        json_record["data"][MandatoryFieldUuid.SUBMITTER_EMAIL.value] == api.user.email
    )
    detail = f"experiment_records/{json_record['id']}/"
    for method in ("put", "patch"):
        api.send(
            method,
            detail,
            {date_field: "2026-01-02"},
            media=media,
            expected=status.HTTP_400_BAD_REQUEST,
        )
    replaced = api.request("put", detail, {date_field: "2026-01-02"})
    assert replaced["data"][date_field] == "2026-01-02"
    modified = api.request("patch", detail, {date_field: "2026-01-03"})
    assert modified["data"][date_field] == "2026-01-03"
    api.request("delete", detail)
    api.request("delete", f"experiments/{experiment['id']}/")


def test_gis_view_lifecycle(domain_api: DomainAPI) -> None:
    api = domain_api
    data = {
        "name": "View",
        "allow_precise_zoom": True,
        "projects": [{"project_id": str(api.project.id), "use_latest": True}],
    }
    created = api.request("post", "user/gis_views/", data, expected=201)
    detail = f"user/gis_views/{created['id']}/"
    api.request("get", "user/gis_views/")
    api.request("get", detail)
    api.request("put", detail, data)
    api.request("patch", detail, {"description": "Updated view"})
    api.request("delete", detail)
