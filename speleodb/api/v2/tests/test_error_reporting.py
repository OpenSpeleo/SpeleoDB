# -*- coding: utf-8 -*-

"""Native error reporting from real GitLab, Git, parser, SQL and filesystem faults.

The SDK's supported event hook observes serialized exceptions. No view, ORM,
compiler, authentication backend, HTTP client or storage implementation is replaced.
"""

from __future__ import annotations

import errno
import pathlib
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from typing import TYPE_CHECKING
from typing import Any

import git
import gitlab.exceptions
import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.models.signals import post_save
from django.db.utils import IntegrityError
from django.test import override_settings
from django.urls import reverse
from git.exc import GitCommandError
from gpxpy.gpx import GPXXMLSyntaxException
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v2.tests.database_constraints import unique_import_names
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import TokenFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.api.v2.tests.test_file_upload_error_handling import BASE_DIR
from speleodb.api.v2.tests.test_file_upload_error_handling import SentryEventTestCase
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import ProjectType
from speleodb.gis.gis_layer_processing import GISLayerProcessingError
from speleodb.gis.models import GISView
from speleodb.gis.models import Landmark
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabError
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.surveys.models import FileFormat
from speleodb.testing.gitlab_pool import canonical_project
from speleodb.testing.gitlab_pool import canonical_user
from speleodb.testing.gitlab_pool import get_pool

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django.http import FileResponse
    from gitlab.v4.objects.projects import Project as GitlabProject
    from rest_framework.response import Response

    from speleodb.git_engine.core import GitRepo
    from speleodb.surveys.models import Project
    from speleodb.users.models import User


@contextmanager
def rejected_gitlab_credentials() -> Iterator[None]:
    """Make the configured GitLab authenticate a real invalid service token."""
    authenticated_client = GitlabManager._gl  # noqa: SLF001
    GitlabManager._gl = None  # noqa: SLF001
    GitlabManager._get_project.cache_clear()  # noqa: SLF001
    GitlabCredentials.get.cache_clear()
    try:
        with override_settings(GITLAB_TOKEN=uuid.uuid4().hex):
            yield
    finally:
        GitlabManager._gl = authenticated_client  # noqa: SLF001
        GitlabManager._get_project.cache_clear()  # noqa: SLF001
        GitlabCredentials.get.cache_clear()


class AuthenticatedSentryTestCase(SentryEventTestCase):
    client: APIClient
    user: User
    auth: str

    def setUp(self) -> None:
        super().setUp()
        assert not connection.in_atomic_block
        self.enterContext(override_settings(DEBUG=False))
        self.user = canonical_user("A")
        token = TokenFactory.create(user=self.user)
        EmailAddress.objects.get_or_create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )
        self.client = APIClient()
        self.auth = f"Token {token.key}"


class ProjectSentryTestCase(AuthenticatedSentryTestCase):
    project: Project
    repo: GitRepo
    remote: GitlabProject
    original_head: str

    def setUp(self) -> None:
        super().setUp()
        directory: str = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(
            override_settings(DJANGO_GIT_PROJECTS_DIR=pathlib.Path(directory))
        )
        self.project = canonical_project(
            role=PermissionLevel.READ_AND_WRITE,
            type=ProjectType.ARIANE,
            exclude_geojson=True,
        )
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project,
            level=PermissionLevel.READ_AND_WRITE,
        )
        # Fail setup if the service is unhealthy; a 429 cannot pass an error test.
        get_pool().prepare(self.project)
        self.repo = self.project.git_repo
        self.addCleanup(self.repo.close)
        remote = GitlabManager._get_project(self.project)  # noqa: SLF001
        assert remote is not None
        self.remote = remote
        target: pathlib.Path = self.repo.path / "ariane.tml"
        target.write_bytes((BASE_DIR / "test_simple.tml").read_bytes())
        self.repo.index.add([str(target)])
        actor: git.Actor = git.Actor("Reporting test", "reporting@example.test")
        self.repo.index.commit(
            "Download integration source", author=actor, committer=actor
        )
        self.repo.git.push("origin", settings.DJANGO_GIT_BRANCH_NAME)
        self.original_head = self.repo.head.commit.hexsha
        assert (
            self.remote.branches.get(settings.DJANGO_GIT_BRANCH_NAME).commit["id"]
            == self.original_head
        )

    def _remove_working_copy(self) -> None:
        self.repo.close()
        shutil.rmtree(self.project.git_repo_dir)

    def _assert_gitlab_authentication_error(self) -> None:
        exception: BaseException = self._reported_exception()
        assert isinstance(exception, GitlabError), exception
        assert isinstance(
            exception.__cause__, gitlab.exceptions.GitlabAuthenticationError
        )
        assert exception.__cause__.response_code == status.HTTP_401_UNAUTHORIZED
        assert not self.project.git_repo_dir.exists()


@pytest.mark.skip_if_lighttest
class FileDownloadSentryTests(ProjectSentryTestCase):
    def _download(self) -> Response | FileResponse:
        return self.client.get(
            reverse(
                "api:v2:project-download",
                kwargs={
                    "id": self.project.id,
                    "fileformat": FileFormat.ARIANE_TML.label.lower(),
                },
            ),
            headers={"authorization": self.auth},
        )

    def test_download_runtime_error_returns_500_with_sentry(self) -> None:
        successful: Response | FileResponse = self._download()
        assert successful.status_code == status.HTTP_200_OK
        successful.close()
        assert not self.sentry_events
        lock: pathlib.Path = pathlib.Path(self.repo.git_dir) / "index.lock"
        lock.write_text("integration checkout lock\n")
        self.addCleanup(lock.unlink, missing_ok=True)

        with self.assertLogs("speleodb.api.v2.views.file", level="ERROR") as logs:
            response: Response | FileResponse = self._download()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        exception: BaseException = self._reported_exception()
        assert isinstance(exception, RuntimeError), exception
        assert isinstance(exception.__cause__, GitCommandError), exception
        assert "index.lock" in str(exception.__cause__)
        assert any("index.lock" in line for line in logs.output)
        assert self.repo.head.commit.hexsha == self.original_head

    def test_download_gitlab_error_returns_500_with_sentry(self) -> None:
        self._remove_working_copy()
        with (
            rejected_gitlab_credentials(),
            self.assertLogs("speleodb.api.v2.views.file", level="ERROR"),
        ):
            response: Response | FileResponse = self._download()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        self._assert_gitlab_authentication_error()


@pytest.mark.skip_if_lighttest
class ProjectExplorerSentryTests(ProjectSentryTestCase):
    def _explore(self, hexsha: str) -> Response:
        return self.client.get(
            reverse(
                "api:v2:project-gitexplorer",
                kwargs={"id": self.project.id, "hexsha": hexsha},
            ),
            headers={"authorization": self.auth},
        )

    def test_git_explorer_missing_commit_returns_500_with_sentry(self) -> None:
        assert self._explore(self.original_head).status_code == status.HTTP_200_OK
        absent_sha: str = uuid.uuid4().hex + uuid.uuid4().hex[:8]
        assert (
            self.repo.git.cat_file(
                "-e", absent_sha, with_exceptions=False, with_extended_output=True
            )[0]
            != 0
        )
        with self.assertLogs(
            "speleodb.api.v2.views.project_explorer", level="ERROR"
        ) as logs:
            response: Response = self._explore(absent_sha)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        exception: BaseException = self._reported_exception()
        assert isinstance(exception, ValueError), exception
        assert absent_sha in str(exception)
        assert any(absent_sha in line for line in logs.output)
        assert absent_sha in response.data["error"]

    def test_git_explorer_gitlab_error_returns_500_with_sentry(self) -> None:
        self._remove_working_copy()
        with (
            rejected_gitlab_credentials(),
            self.assertLogs("speleodb.api.v2.views.project_explorer", level="ERROR"),
        ):
            response: Response = self._explore(self.original_head)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        self._assert_gitlab_authentication_error()


class ProjectDetailSentryTests(AuthenticatedSentryTestCase):
    def test_project_detail_reads_persisted_metadata_without_gitlab(self) -> None:
        # This serializer reads SQL metadata. Its old forced GitlabError was not
        # reachable behavior; prove its actual independence from service auth.
        project: Project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            project=project, target=self.user, level=PermissionLevel.READ_ONLY
        )
        with rejected_gitlab_credentials():
            response: Response = self.client.get(
                reverse("api:v2:project-detail", kwargs={"id": project.id}),
                headers={"authorization": self.auth},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(project.id)
        assert response.data["name"] == project.name
        assert not self.sentry_events
        assert not project.git_repo_dir.exists()


class LandmarkImportSentryTestCase(AuthenticatedSentryTestCase):
    written_landmarks: list[uuid.UUID]

    def setUp(self) -> None:
        super().setUp()
        self.written_landmarks = []
        post_save.connect(self._record_landmark, sender=Landmark)
        self.addCleanup(post_save.disconnect, self._record_landmark, sender=Landmark)

    def _record_landmark(
        self, instance: Landmark, created: bool, **kwargs: Any
    ) -> None:
        if created:
            self.written_landmarks.append(instance.id)

    def _assert_constraint_rollback(self, response: Response) -> None:
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        exception: BaseException = self._reported_exception()
        assert isinstance(exception, IntegrityError), exception
        assert "unique" in str(exception).lower()
        # Native post_save proves one INSERT succeeded before the second failed.
        assert len(self.written_landmarks) == 1
        assert not connection.in_atomic_block
        assert not Landmark.objects.filter(created_by=self.user.email).exists()


class GPXImportSentryTests(LandmarkImportSentryTestCase):
    def _import(self, content: bytes) -> Response:
        return self.client.put(
            reverse("api:v2:gpx-import"),
            {
                "file": SimpleUploadedFile(
                    "test.gpx", content, content_type="application/gpx+xml"
                )
            },
            format="multipart",
            headers={"authorization": self.auth},
        )

    def test_gpx_import_failure_returns_500_with_sentry(self) -> None:
        with self.assertLogs("speleodb.api.v2.views.gpx_import", level="ERROR"):
            response: Response = self._import(b"not valid gpx")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert isinstance(self._reported_exception(), GPXXMLSyntaxException)
        assert self.written_landmarks == []

    def test_gpx_import_failure_does_not_commit_partial_landmarks(self) -> None:
        content: bytes = (
            b'<gpx version="1.1" creator="SpeleoDB" xmlns="http://www.topografix.com/GPX/1/1">'
            b'<wpt lat="20.1" lon="-87.5"><name>Duplicate waypoint</name></wpt>'
            b'<wpt lat="20.2" lon="-87.6"><name>Duplicate waypoint</name></wpt></gpx>'
        )
        with (
            unique_import_names(Landmark, created_by=self.user.email),
            self.assertLogs("speleodb.api.v2.views.gpx_import", level="ERROR"),
        ):
            response: Response = self._import(content)

        self._assert_constraint_rollback(response)


class KMLImportSentryTests(LandmarkImportSentryTestCase):
    def _import(self, content: bytes) -> Response:
        return self.client.put(
            reverse("api:v2:kml-kmz-import"),
            {
                "file": SimpleUploadedFile(
                    "test.kml",
                    content,
                    content_type="application/vnd.google-earth.kml+xml",
                )
            },
            format="multipart",
            headers={"authorization": self.auth},
        )

    def test_kml_import_failure_returns_422_with_sentry(self) -> None:
        with self.assertLogs("speleodb.api.v2.views.kml_kmz_import", level="ERROR"):
            response: Response = self._import(b"not valid kml")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert isinstance(self._reported_exception(), GISLayerProcessingError)
        assert self.written_landmarks == []

    def test_kml_import_failure_does_not_commit_partial_landmarks(self) -> None:
        content: bytes = (
            b'<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
            b"<Placemark><name>Duplicate landmark</name><Point>"
            b"<coordinates>-87.5,20.1</coordinates></Point></Placemark>"
            b"<Placemark><name>Duplicate landmark</name><Point>"
            b"<coordinates>-87.6,20.2</coordinates></Point></Placemark></Document></kml>"
        )
        with (
            unique_import_names(Landmark, created_by=self.user.email),
            self.assertLogs("speleodb.api.v2.views.kml_kmz_import", level="ERROR"),
        ):
            response: Response = self._import(content)

        self._assert_constraint_rollback(response)


class GISViewSentryTests(AuthenticatedSentryTestCase):
    def test_gis_view_data_and_missing_view_use_real_serializer(self) -> None:
        # The former test forced the serializer constructor to raise. Exercise
        # actual SQL-backed metadata and missing-object handling instead.
        gis_view: GISView = GISView.objects.create(
            name="Reporting integration", owner=self.user, allow_precise_zoom=False
        )
        response: Response = self.client.get(
            reverse("api:v2:gis-view-data", kwargs={"id": gis_view.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["view_id"] == str(gis_view.id)
        assert response.data["view_name"] == gis_view.name
        assert response.data["geojson_files"] == []
        missing: Response = self.client.get(
            reverse("api:v2:gis-view-data", kwargs={"id": uuid.uuid4()}),
            headers={"authorization": self.auth},
        )
        assert missing.status_code == status.HTTP_404_NOT_FOUND
        assert not self.sentry_events


class ToolsDMPSentryTests(AuthenticatedSentryTestCase):
    def test_dmp_filesystem_error_returns_500_with_sentry(self) -> None:
        # Django limits characters, while the real filesystem limits UTF-8 bytes.
        # This reaches the actual file write and fails with ENAMETOOLONG.
        filename: str = "é" * 130 + ".dmp"
        with self.assertLogs("speleodb.api.v2.views.tools", level="ERROR") as logs:
            response: Response = self.client.post(
                reverse("api:v2:tool-dmp2json"),
                {"file": SimpleUploadedFile(filename, b"nonempty survey file")},
                format="multipart",
                headers={"authorization": self.auth},
            )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        exception: BaseException = self._reported_exception()
        assert isinstance(exception, OSError), exception
        assert exception.errno == errno.ENAMETOOLONG
        assert exception.filename is not None
        assert pathlib.Path(exception.filename).name == filename
        assert not pathlib.Path(exception.filename).parent.exists()
        assert any("File name too long" in line for line in logs.output)
