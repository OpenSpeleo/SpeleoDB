# -*- coding: utf-8 -*-

"""Tests that every API view returning HTTP 500 properly reports to Sentry,
logs the traceback, and rolls back DB writes when applicable.

Each test mocks a failure inside the view's try block and verifies
``sentry_sdk.capture_exception`` is called with the correct exception.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.views.gis_view import GISViewDataApiView
from speleodb.api.v2.views.tools import ToolDMP2JSON
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Landmark
from speleodb.git_engine.exceptions import GitBaseError
from speleodb.git_engine.gitlab_manager import GitlabError
from speleodb.surveys.models import FileFormat

# ---------------------------------------------------------------------------
# FileDownloadView (file.py)
# ---------------------------------------------------------------------------


@pytest.mark.skip_if_lighttest
class FileDownloadSentryTests(BaseAPIProjectTestCase):
    """FileDownloadView 500 paths must log and report to Sentry."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )

    def _do_download(self) -> Any:
        return self.client.get(
            reverse(
                "api:v2:project-download",
                kwargs={
                    "id": self.project.id,
                    "fileformat": FileFormat.ARIANE_TML.label.lower(),
                },
            ),
            headers={"authorization": f"{self.header_prefix}{self.token.key}"},
        )

    @patch(
        "speleodb.api.v2.views.file.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_download_runtime_error_returns_500_with_sentry(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """RuntimeError during download should produce 500 + Sentry event."""
        with patch(
            "speleodb.processors.AutoSelector.get_download_processor",
            side_effect=RuntimeError("simulated download failure"),
        ):
            response = self._do_download()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_sentry.assert_called_once()
        assert isinstance(mock_sentry.call_args[0][0], RuntimeError)

    @patch(
        "speleodb.api.v2.views.file.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_download_gitlab_error_returns_500_with_sentry(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """GitlabError during download should produce 500 + Sentry event."""
        with patch(
            "speleodb.processors.AutoSelector.get_download_processor",
            side_effect=GitlabError("simulated gitlab outage"),
        ):
            response = self._do_download()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_sentry.assert_called_once()
        assert isinstance(mock_sentry.call_args[0][0], GitlabError)


# ---------------------------------------------------------------------------
# ProjectGitExplorerApiView (project_explorer.py)
# ---------------------------------------------------------------------------


@pytest.mark.skip_if_lighttest
class ProjectExplorerSentryTests(BaseAPIProjectTestCase):
    """ProjectGitExplorerApiView 500 paths must log and report to Sentry."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )

    @patch(
        "speleodb.api.v2.views.project_explorer.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_git_explorer_checkout_error_returns_500_with_sentry(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """Git checkout error should produce 500 + Sentry event."""
        fake_sha = "a" * 40
        with patch.object(
            type(self.project),
            "checkout_commit_or_default_pull_branch",
            side_effect=GitBaseError("simulated checkout failure"),
        ):
            response = self.client.get(
                reverse(
                    "api:v2:project-gitexplorer",
                    kwargs={"id": self.project.id, "hexsha": fake_sha},
                ),
                headers={"authorization": f"{self.header_prefix}{self.token.key}"},
            )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_sentry.assert_called_once()
        assert isinstance(mock_sentry.call_args[0][0], GitBaseError)

    @patch(
        "speleodb.api.v2.views.project_explorer.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_git_explorer_gitlab_error_returns_500_with_sentry(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """GitlabError during explorer should produce 500 + Sentry event."""
        fake_sha = "b" * 40
        with patch.object(
            type(self.project),
            "checkout_commit_or_default_pull_branch",
            side_effect=GitlabError("simulated gitlab outage"),
        ):
            response = self.client.get(
                reverse(
                    "api:v2:project-gitexplorer",
                    kwargs={"id": self.project.id, "hexsha": fake_sha},
                ),
                headers={"authorization": f"{self.header_prefix}{self.token.key}"},
            )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_sentry.assert_called_once()


# ---------------------------------------------------------------------------
# ProjectSpecificApiView (project.py)
# ---------------------------------------------------------------------------


@pytest.mark.skip_if_lighttest
class ProjectDetailSentryTests(BaseAPIProjectTestCase):
    """ProjectSpecificApiView 500 paths must report to Sentry."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_ONLY,
            permission_type=PermissionType.USER,
        )

    @patch(
        "speleodb.api.v2.views.project.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_project_detail_gitlab_error_returns_500_with_sentry(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """GitlabError during project detail should produce 500 + Sentry."""
        with patch(
            "speleodb.api.v2.serializers.project.ProjectSerializer.to_representation",
            side_effect=GitlabError("simulated gitlab outage"),
        ):
            response = self.client.get(
                reverse(
                    "api:v2:project-detail",
                    kwargs={"id": self.project.id},
                ),
                headers={"authorization": f"{self.header_prefix}{self.token.key}"},
            )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_sentry.assert_called_once()


# ---------------------------------------------------------------------------
# GPX import (gpx_import.py)
# ---------------------------------------------------------------------------


@pytest.mark.skip_if_lighttest
class GPXImportSentryTests(BaseAPIProjectTestCase):
    """GPXImportView 500 paths must log, report to Sentry, and rollback."""

    def _do_gpx_import(self, content: bytes = b"bad content") -> Any:

        gpx_file = SimpleUploadedFile(
            "test.gpx", content, content_type="application/gpx+xml"
        )
        return self.client.put(
            reverse("api:v2:gpx-import"),
            {"file": gpx_file},
            format="multipart",
            headers={"authorization": f"{self.header_prefix}{self.token.key}"},
        )

    @patch(
        "speleodb.api.v2.views.gpx_import.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_gpx_import_failure_returns_500_with_sentry(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """An exception during GPX import should produce 500 + Sentry event."""
        response = self._do_gpx_import(b"not valid gpx")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_sentry.assert_called_once()

    @patch(
        "speleodb.api.v2.views.gpx_import.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_gpx_import_failure_does_not_commit_partial_landmarks(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """GPX import failure should not commit partial Landmark rows."""
        landmarks_before = Landmark.objects.count()

        response = self._do_gpx_import(b"not valid gpx")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert Landmark.objects.count() == landmarks_before


# ---------------------------------------------------------------------------
# KML/KMZ import (kml_kmz_import.py)
# ---------------------------------------------------------------------------


@pytest.mark.skip_if_lighttest
class KMLImportSentryTests(BaseAPIProjectTestCase):
    """KML_KMZ_ImportView 500 paths must log, report to Sentry, and rollback."""

    def _do_kml_import(self, content: bytes = b"bad content") -> Any:

        kml_file = SimpleUploadedFile(
            "test.kml", content, content_type="application/vnd.google-earth.kml+xml"
        )
        return self.client.put(
            reverse("api:v2:kml-kmz-import"),
            {"file": kml_file},
            format="multipart",
            headers={"authorization": f"{self.header_prefix}{self.token.key}"},
        )

    @patch(
        "speleodb.api.v2.views.kml_kmz_import.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_kml_import_failure_returns_500_with_sentry(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """An exception during KML import should produce 500 + Sentry event."""
        response = self._do_kml_import(b"not valid kml")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_sentry.assert_called_once()

    @patch(
        "speleodb.api.v2.views.kml_kmz_import.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_kml_import_failure_does_not_commit_partial_landmarks(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """KML import failure should not commit partial Landmark rows."""
        landmarks_before = Landmark.objects.count()

        response = self._do_kml_import(b"not valid kml")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert Landmark.objects.count() == landmarks_before


# ---------------------------------------------------------------------------
# GIS View (gis_view.py)
# ---------------------------------------------------------------------------


class GISViewSentryTests(TestCase):
    """GISViewDataApiView and PublicGISViewGeoJSONApiView 500 paths
    must log and report to Sentry."""

    @patch(
        "speleodb.api.v2.views.gis_view.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_gis_view_data_error_returns_500_with_sentry(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """Error in GISViewDataApiView should produce 500 + Sentry event."""
        with patch(
            "speleodb.api.v2.views.gis_view.GISViewDataSerializer",
            side_effect=RuntimeError("serializer failure"),
        ):
            view = GISViewDataApiView()
            mock_request = MagicMock()
            mock_request.query_params = {}

            mock_gis_view = MagicMock()
            with patch.object(view, "get_object", return_value=mock_gis_view):
                response = view.get(mock_request)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_sentry.assert_called_once()


# ---------------------------------------------------------------------------
# Tools (tools.py)
# ---------------------------------------------------------------------------


class ToolsDMPSentryTests(TestCase):
    """ToolDMP2JSON 500 paths must log and report to Sentry."""

    @patch(
        "speleodb.api.v2.views.tools.sentry_sdk.capture_exception",
        autospec=True,
    )
    def test_dmp_parse_error_returns_500_with_sentry(
        self,
        mock_sentry: MagicMock,
    ) -> None:
        """An unexpected error during DMP parsing should produce 500 + Sentry."""

        view = ToolDMP2JSON()
        mock_request = MagicMock()
        mock_request.FILES = {
            "file": SimpleUploadedFile("test.dmp", b"invalid dmp content")
        }

        with patch(
            "speleodb.api.v2.views.tools.DMPFile.from_dmp",
            side_effect=OSError("simulated I/O failure"),
        ):
            response = view.post(mock_request)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_sentry.assert_called_once()
        assert isinstance(mock_sentry.call_args[0][0], OSError)
