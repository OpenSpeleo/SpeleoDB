"""Real core API workflows and the normalized inputs described by OpenAPI."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any
from typing import cast
from urllib.parse import urlencode

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.views.user import UserAutocompleteView
from speleodb.background_jobs.models import BackgroundJob
from speleodb.background_jobs.models import JobArtifact
from speleodb.background_jobs.models import JobAttempt
from speleodb.background_jobs.models import JobState
from speleodb.common.enums import PermissionLevel
from speleodb.testing.api_contract import assert_api_response
from speleodb.testing.api_contract import contract_schema
from speleodb.users.tests.factories import UserFactory

ARTIFACTS = Path(__file__).parent / "artifacts"


def resolve_schema(schema: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in schema:
        return cast(
            "dict[str, Any]",
            contract_schema()["components"]["schemas"][
                schema["$ref"].rsplit("/", 1)[1]
            ],
        )
    return schema


def request_schema(path: str, method: str, media: str) -> dict[str, Any]:
    return resolve_schema(
        contract_schema()["paths"][path][method]["requestBody"]["content"][media][
            "schema"
        ]
    )


class TestCoreAPIContract(BaseAPIProjectTestCase):
    """Exercise the actual v2 wire at corrected contract boundaries."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(PermissionLevel.ADMIN, PermissionType.USER)

    def request(
        self,
        method: str,
        route: str,
        data: Any = None,
        *,
        kwargs: dict[str, Any] | None = None,
        expected: int = status.HTTP_200_OK,
        media: str = "json",
    ) -> Any:
        options: dict[str, Any] = {"headers": {"authorization": self.auth}}
        if method != "get":
            options["format"] = media
        response = getattr(self.client, method)(
            reverse(f"api:v2:{route}", kwargs=kwargs),
            data=data,
            **options,
        )
        assert response.status_code == expected, getattr(response, "data", None)
        assert_api_response(response)
        return response

    def test_export_lifecycle_and_redirect_headers(self) -> None:
        created = self.request("post", "user-exports", expected=202).json()
        job = BackgroundJob.objects.get(pk=created["id"])
        self.request("get", "user-exports", {"page": "last"})
        self.request("get", "user-export-detail", kwargs={"id": job.pk})
        job.state = JobState.FAILED
        job.save(update_fields=["state"])
        self.request("post", "user-export-retry", kwargs={"id": job.pk}, expected=202)
        job.refresh_from_db()
        attempt = JobAttempt.objects.get(job=job, number=2)
        now = timezone.now()
        JobArtifact.objects.create(
            job=job,
            attempt=attempt,
            object_key=f"exports/{self.user.pk}/{job.pk}/{attempt.pk}.zip",
            filename="contract-export.zip",
            size_bytes=123,
            sha256="a" * 64,
            ready_at=now,
            expires_at=now + timedelta(hours=1),
        )
        job.state = JobState.READY
        job.save(update_fields=["state"])
        response = self.request(
            "get",
            "user-export-download",
            kwargs={"id": job.pk},
            expected=302,
        )
        assert response["Location"].startswith(("http://", "https://"))
        assert response["Cache-Control"] == "private, no-store"
        assert response["Referrer-Policy"] == "no-referrer"

    def test_spreadsheet_tools_with_measured_and_terminal_rows(self) -> None:
        dmp_body = {
            "shots": [
                {
                    "depth": False,
                    "length": " 2_0 ",
                    "azimuth": " 9_0 ",
                    "left": True,
                    "right": "",
                    "up": "",
                    "down": "",
                },
                {"depth": 11},
            ],
            "survey_date": "2025-01-01",
            "unit": "meters",
            "direction": "in",
        }
        compass_body = {
            "shots": [
                {
                    "station": "A",
                    "depth": False,
                    "length": " 2_0 ",
                    "azimuth": False,
                    "flags": "#|PPCLXS#",
                },
                {
                    "station": "B",
                    "depth": 11,
                    "length": False,
                    "azimuth": [],
                    "left": {},
                },
            ],
            "survey_date": "2025-01-01",
            "unit": "meters",
            "cave_name": "Contract cave",
            "survey_name": "Contract survey",
            "survey_team": [],
            "comment": "",
            "latitude": 20,
            "longitude": -87,
        }
        for route, body in (
            ("tool-xls2dmp", dmp_body),
            ("tool-xls2compass", compass_body),
        ):
            response = self.request("post", route, body)
            assert b"".join(response.streaming_content)
        degenerate = self.request("post", "tool-xls2dmp", {**dmp_body, "shots": [{}]})
        assert b"".join(degenerate.streaming_content)
        missing_lrud = {
            **dmp_body,
            "shots": [{"depth": 10, "length": 20, "azimuth": 90}, {"depth": 11}],
        }
        self.request("post", "tool-xls2dmp", missing_lrud, expected=400)
        self.request(
            "post", "tool-xls2compass", {**compass_body, "latitude": 91}, expected=400
        )

    def test_dmp_tools_preserve_json_encoded_configuration(self) -> None:
        source = (ARTIFACTS / "test_v5.dmp").read_bytes()
        converted = self.request(
            "post",
            "tool-dmp2json",
            {"file": SimpleUploadedFile("source.dmp", source)},
            media="multipart",
        )
        assert json.loads(b"".join(converted.streaming_content))
        configuration = {
            "fix_dmp": False,
            "survey_date": None,
            "length_scaling": 1,
            "compass_offset": 0,
            "reverse_direction": False,
            "depth_offset": 0,
            "depth_offset_unit": "meters",
        }
        repaired = self.request(
            "post",
            "tool-dmp-doctor",
            {
                "file": SimpleUploadedFile("source.dmp", source),
                "data": json.dumps(configuration),
            },
            media="multipart",
        )
        assert b"".join(repaired.streaming_content)
        self.request(
            "post",
            "tool-dmp-doctor",
            {
                "file": SimpleUploadedFile("source.dmp", source),
                "data": json.dumps({**configuration, "length_scaling": 0}),
            },
            media="multipart",
            expected=400,
        )

    def test_project_normalized_coordinates_and_server_owned_creator(self) -> None:
        kwargs = {"id": self.project.pk}
        coordinate_pairs = (
            {"latitude": "30°15'03\"N", "longitude": "45°30'15\"W"},
            {"latitude": "3_0.123456789", "longitude": "-4_5.123456789"},
            {"latitude": True, "longitude": True},
            {"latitude": "30.123456789", "longitude": "-45.123456789"},
        )
        for coordinates in coordinate_pairs:
            media_types = (
                ("json",)
                if coordinates["latitude"] is True
                else ("json", "multipart", "urlencoded")
            )
            for media in media_types:
                url = reverse("api:v2:project-detail", kwargs=kwargs)
                options: dict[str, Any] = {"format": media}
                data: Any = coordinates
                if media == "urlencoded":
                    options = {"content_type": "application/x-www-form-urlencoded"}
                    data = urlencode(coordinates)
                response = self.client.patch(
                    url, data, headers={"authorization": self.auth}, **options
                )
                assert response.status_code == status.HTTP_200_OK, response.content
                assert_api_response(response)
                if coordinates["latitude"] is True:
                    assert response.json()["latitude"] == 1
                    assert response.json()["longitude"] == 1
        self.request(
            "patch",
            "project-detail",
            {"created_by": self.user.email},
            kwargs=kwargs,
            expected=400,
        )
        self.request(
            "patch",
            "project-detail",
            {"latitude": False, "longitude": False},
            kwargs=kwargs,
            expected=400,
        )
        self.project.refresh_from_db()
        assert self.project.latitude is not None
        assert self.project.longitude is not None
        assert float(self.project.latitude) == pytest.approx(30.1234568)
        assert float(self.project.longitude) == pytest.approx(-45.1234568)

    def test_upload_count_is_rejected_before_any_git_access(self) -> None:
        self.project.acquire_mutex(self.user)
        self.request(
            "put",
            "project-upload",
            {
                "message": "Too many files",
                "artifact": [
                    SimpleUploadedFile(f"artifact-{index}.txt", b"x")
                    for index in range(settings.DJANGO_UPLOAD_TOTAL_FILES_LIMIT + 1)
                ],
            },
            kwargs={"id": self.project.pk, "fileformat": "auto"},
            media="multipart",
            expected=400,
        )

    def test_autocomplete_boundaries(self) -> None:
        for index in range(UserAutocompleteView.MAXIMUM_RESULTS + 1):
            UserFactory.create(
                email=f"core-autocomplete-{index}@example.test", name="Zed user"
            )
        self.request("get", "user-autocomplete", {"query": "Ze"}, expected=400)
        results = self.request("get", "user-autocomplete", {"query": " Zed "}).json()
        assert len(results) == UserAutocompleteView.MAXIMUM_RESULTS


def test_corrected_core_input_metadata() -> None:
    paths = contract_schema()["paths"]
    for route in ("dmp-doctor", "dmp2json", "xls2compass", "xls2dmp"):
        assert paths[f"/api/v2/tools/{route}/"]["post"]["requestBody"]["required"]
    doctor = request_schema("/api/v2/tools/dmp-doctor/", "post", "multipart/form-data")
    field = doctor["properties"]["data"]
    assert field["type"] == "string"
    decoded = resolve_schema(field["x-json-schema"])
    assert set(decoded["required"]) == {
        "fix_dmp",
        "survey_date",
        "length_scaling",
        "compass_offset",
        "reverse_direction",
        "depth_offset",
        "depth_offset_unit",
    }
    assert decoded["properties"]["length_scaling"]["minimum"] == 0
    assert decoded["properties"]["length_scaling"]["exclusiveMinimum"] is True
    assert json.loads(field["example"])["survey_date"] is None
    upload = request_schema(
        "/api/v2/projects/{id}/upload/{fileformat}/", "put", "multipart/form-data"
    )
    assert (
        upload["properties"]["artifact"]["maxItems"]
        == settings.DJANGO_UPLOAD_TOTAL_FILES_LIMIT
    )
    for method in ("put", "patch"):
        for media in (
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data",
        ):
            project = request_schema("/api/v2/projects/{id}/", method, media)
            assert "created_by" not in project["properties"]
    autocomplete = paths["/api/v2/user/autocomplete/"]["get"]
    query = next(
        parameter
        for parameter in autocomplete["parameters"]
        if parameter["name"] == "query"
    )
    assert query["schema"]["minLength"] == UserAutocompleteView.MINIMUM_QUERY_LEN
    results = autocomplete["responses"]["200"]["content"]["application/json"]["schema"]
    assert results["maxItems"] == UserAutocompleteView.MAXIMUM_RESULTS
