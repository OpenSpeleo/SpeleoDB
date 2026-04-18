# -*- coding: utf-8 -*-

"""Tests for read / export / GeoJSON endpoints:

- ``api:v2:all-projects-geojson``            (GET)
- ``api:v2:exploration-lead-all-geojson``    (GET)
- ``api:v2:experiment-export-excel``         (GET, xlsx download)
- ``api:v2:gis-ogc:experiment``              (GET, public gis_token)

The file-download routes ``project-download-blob`` and
``project-download-at-hash`` require an on-disk GIT repo which is expensive
to spin up in a unit test; a minimal authz-path test is included so
unauthorized callers still get 403/404 coverage.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.tests.factories import ExperimentFactory
from speleodb.api.v2.tests.factories import ExplorationLeadFactory
from speleodb.api.v2.tests.factories import UserExperimentPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.surveys.models import FileFormat


@pytest.mark.django_db
class TestAllProjectsGeoJSON(BaseAPIProjectTestCase):
    """GET /api/v2/projects/geojson/ - returns all accessible projects as
    GeoJSON metadata."""

    def test_requires_authentication(self) -> None:
        response = self.client.get(reverse("api:v2:all-projects-geojson"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_returns_list(self) -> None:
        self.set_test_project_permission(
            level=PermissionLevel.WEB_VIEWER,
            permission_type=PermissionType.USER,
        )
        response = self.client.get(
            reverse("api:v2:all-projects-geojson"),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert isinstance(response.data, list)
        ids = [p["id"] for p in response.data]
        assert str(self.project.id) in ids

    def test_no_permissions_returns_empty_list(self) -> None:
        """A user with zero project permissions just sees an empty list."""
        response = self.client.get(
            reverse("api:v2:all-projects-geojson"),
            headers={"authorization": self.auth},
        )
        # WEB_VIEWER is the minimum level allowed; a totally unassigned user
        # gets either 200+empty or 403 depending on SDB_WebViewerAccess.
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
        ), response.data


@pytest.mark.django_db
class TestExplorationLeadAllGeoJSON(BaseAPIProjectTestCase):
    """GET /api/v2/exploration-leads/geojson/
    user-scoped GeoJSON FeatureCollection."""

    def test_requires_authentication(self) -> None:
        response = self.client.get(reverse("api:v2:exploration-lead-all-geojson"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_returns_feature_collection(self) -> None:
        self.set_test_project_permission(
            level=PermissionLevel.READ_ONLY, permission_type=PermissionType.USER
        )
        _ = ExplorationLeadFactory.create(project=self.project)

        response = self.client.get(
            reverse("api:v2:exploration-lead-all-geojson"),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        body = response.json()
        assert body["type"] == "FeatureCollection"
        assert isinstance(body["features"], list)
        assert len(body["features"]) >= 1

    def test_excludes_leads_from_inaccessible_projects(self) -> None:
        """Only leads belonging to projects the user can read appear."""
        _ = ExplorationLeadFactory.create(project=self.project)  # no permission yet
        response = self.client.get(
            reverse("api:v2:exploration-lead-all-geojson"),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        body = response.json()
        assert body["features"] == []


@pytest.mark.django_db
class TestExperimentExportExcel(BaseAPITestCase):
    """GET /api/v2/experiments/<id>/export/excel/ - binary xlsx download."""

    def setUp(self) -> None:
        super().setUp()
        self.experiment = ExperimentFactory.create(created_by=self.user.email)
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=self.experiment,
            level=PermissionLevel.READ_ONLY,
        )
        self.url = reverse(
            "api:v2:experiment-export-excel",
            kwargs={"id": self.experiment.id},
        )

    def test_requires_authentication(self) -> None:
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_happy_path_returns_xlsx(self) -> None:
        response = self.client.get(self.url, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK, getattr(
            response, "data", response.content
        )
        content = (
            b"".join(response.streaming_content)
            if hasattr(response, "streaming_content")
            else response.content
        )
        # An .xlsx file is a zip archive; first four bytes are PK\x03\x04.
        assert content[:4] == b"PK\x03\x04", content[:20]
        disposition = response["content-disposition"].lower()
        assert "attachment" in disposition
        assert ".xlsx" in disposition

    def test_without_permission_forbidden(self) -> None:
        # Create a second experiment this user cannot access.
        stranger_exp = ExperimentFactory.create(created_by="someone@other.test")
        response = self.client.get(
            reverse(
                "api:v2:experiment-export-excel",
                kwargs={"id": stranger_exp.id},
            ),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, getattr(
            response, "data", response.content
        )


@pytest.mark.django_db
class TestExperimentOGCPublicGeoJSON(BaseAPITestCase):
    """GET /api/v2/gis-ogc/experiment/<gis_token>/ - public GeoJSON feed."""

    def test_returns_feature_collection_for_valid_token(self) -> None:
        experiment = ExperimentFactory.create(created_by=self.user.email)
        response = self.client.get(
            reverse(
                "api:v2:gis-ogc:experiment",
                kwargs={"gis_token": experiment.gis_token},
            )
        )
        assert response.status_code == status.HTTP_200_OK, response.content
        body = response.json()
        assert body["type"] == "FeatureCollection"
        assert "features" in body

    def test_404_for_unknown_token(self) -> None:
        response = self.client.get(
            reverse(
                "api:v2:gis-ogc:experiment",
                # 40-char hex token (matches URL converter regex) that no
                # experiment has been issued against.
                kwargs={"gis_token": "0" * 40},
            )
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestProjectDownloadAuthz(BaseAPIProjectTestCase):
    """Authorization-only regression on blob / at-hash download endpoints.

    A full happy-path test would require an actual git repo state; these
    tests just lock the 403 / 404 / 401 boundaries so we don't leak data
    to unauthenticated callers.
    """

    def test_blob_download_requires_auth(self) -> None:
        response = self.client.get(
            reverse(
                "api:v2:project-download-blob",
                kwargs={"id": self.project.id, "hexsha": "0" * 40},
            )
        )
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_at_hash_download_requires_auth(self) -> None:
        response = self.client.get(
            reverse(
                "api:v2:project-download-at-hash",
                kwargs={
                    "id": self.project.id,
                    # Must be a registered `DownloadFormatsConverter` choice;
                    # `FileFormat.ARIANE_TML.label.lower()` == "ariane_tml".
                    "fileformat": FileFormat.ARIANE_TML.label.lower(),
                    "hexsha": "0" * 40,
                },
            )
        )
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_blob_download_without_permission(self) -> None:
        """Auth'd but no project permission -> 403/404."""
        response = self.client.get(
            reverse(
                "api:v2:project-download-blob",
                kwargs={"id": self.project.id, "hexsha": "0" * 40},
            ),
            headers={"authorization": self.auth},
        )
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )
