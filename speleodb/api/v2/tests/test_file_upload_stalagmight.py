"""STALX uploads retain native source bytes across actual GitLab revisions."""

from __future__ import annotations

import contextlib
import io
import re
import sqlite3
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.http import StreamingHttpResponse
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status
from rest_framework.response import Response

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import ProjectType
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import Format
from speleodb.surveys.models import ProjectCommit
from speleodb.surveys.models import TeamProjectPermission
from speleodb.surveys.models import UserProjectPermission
from speleodb.testing.gitlab_pool import get_pool
from speleodb.testing.stalagmight import stalagmight_bytes

MAX_SYNTHETIC_PAYLOAD_BYTES = 100_000


@pytest.mark.skip_if_lighttest
class TestStalagmightFiles(BaseAPIProjectTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )
        self.project.type = ProjectType.STALAGMIGHT
        self.project.exclude_geojson = False
        self.project.save(update_fields=["type", "exclude_geojson"])
        get_pool().prepare(self.project)
        self.project.acquire_mutex(self.user)
        self.source = stalagmight_bytes()

    def _upload(
        self,
        payload: bytes,
        *,
        fileformat: FileFormat = FileFormat.STALAGMIGHT,
        message: str = "Stalagmight source revision",
    ) -> Response | HttpResponse:
        response = self.client.put(
            reverse(
                "api:v2:project-upload",
                kwargs={"id": self.project.id, "fileformat": fileformat.label.lower()},
            ),
            {
                "artifact": SimpleUploadedFile(
                    "client-project.stalx", payload, "application/vnd.sqlite3"
                ),
                "message": message,
            },
            format="multipart",
            headers={"authorization": self.auth},
        )
        assert isinstance(response, (Response, HttpResponse))
        return response

    def _download(
        self, *, hexsha: str | None = None, fileformat: str = "stalagmight"
    ) -> HttpResponse | StreamingHttpResponse:
        kwargs = {"id": self.project.id, "fileformat": fileformat}
        if hexsha is not None:
            kwargs["hexsha"] = hexsha
        route = "project-download-at-hash" if hexsha else "project-download"
        return self.client.get(
            reverse(f"api:v2:{route}", kwargs=kwargs),
            headers={"authorization": self.auth},
        )

    @staticmethod
    def _bytes(response: HttpResponse | StreamingHttpResponse) -> bytes:
        if isinstance(response, StreamingHttpResponse):
            assert not response.is_async
            return b"".join(response.streaming_content)  # type: ignore[arg-type]
        return bytes(response.content)

    @parameterized.expand([FileFormat.STALAGMIGHT, FileFormat.AUTO])
    def test_upload_download_and_identical_retry(self, fileformat: FileFormat) -> None:
        uploaded = self._upload(self.source, fileformat=fileformat)

        assert isinstance(uploaded, Response)
        assert uploaded.status_code == status.HTTP_200_OK, uploaded.data
        assert uploaded.data["files"] == ["stalagmight.stalx"]
        assert uploaded.data["project"]["type"] == "STALAGMIGHT"
        assert (
            Format.objects.get(project=self.project).raw_format
            == FileFormat.STALAGMIGHT
        )
        commit = ProjectCommit.objects.get(
            pk=uploaded.data["hexsha"], project=self.project
        )
        assert commit.message.strip() == "Stalagmight source revision"
        assert commit.author_email == self.user.email
        assert {
            "name": "STALAGMIGHT",
            "download_url": reverse(
                "api:v2:project-download-at-hash",
                kwargs={
                    "id": self.project.id,
                    "hexsha": commit.id,
                    "fileformat": "stalagmight",
                },
            ),
        } in uploaded.data["project"]["latest_commit"]["formats"]
        assert any(entry["path"] == "stalagmight.stalx" for entry in commit.tree)

        downloaded = self._download()
        assert downloaded.status_code == status.HTTP_200_OK
        assert downloaded["Content-Type"] == "application/octet-stream"
        assert re.search(
            r'filename="[a-z0-9-]+__\d{4}-\d{2}-\d{2}_\d{2}h\d{2}\.stalx"',
            downloaded["Content-Disposition"],
        )
        assert self._bytes(downloaded) == self.source

        commit_ids = set(
            ProjectCommit.objects.filter(project=self.project).values_list(
                "id", flat=True
            )
        )
        unchanged = self._upload(
            self.source, fileformat=fileformat, message="Same source"
        )
        assert unchanged.status_code == status.HTTP_304_NOT_MODIFIED
        assert (
            set(
                ProjectCommit.objects.filter(project=self.project).values_list(
                    "id", flat=True
                )
            )
            == commit_ids
        )
        repo = self.project.git_repo
        assert repo.head.commit.hexsha == commit.id
        assert not repo.is_dirty(untracked_files=True)

    def test_latest_historical_blob_and_dump_preserve_each_revision(self) -> None:
        first = self._upload(self.source)
        assert isinstance(first, Response)
        assert first.status_code == status.HTTP_200_OK, first.data
        first_sha = str(first.data["hexsha"])
        with contextlib.closing(sqlite3.connect(":memory:")) as database:
            database.execute("CREATE TABLE survey (name TEXT)")
            database.execute("INSERT INTO survey VALUES ('Second revision')")
            database.commit()
            second_source = database.serialize()
        assert len(second_source) <= MAX_SYNTHETIC_PAYLOAD_BYTES
        second = self._upload(second_source, message="Changed SQLite source")
        assert isinstance(second, Response)
        assert second.status_code == status.HTTP_200_OK, second.data
        second_sha = str(second.data["hexsha"])
        assert second_sha != first_sha
        second_commit = ProjectCommit.objects.get(pk=second_sha)
        assert second_commit.parent_ids == [first_sha]

        historical = self._download(hexsha=first_sha)
        assert historical.status_code == status.HTTP_200_OK
        assert self._bytes(historical) == self.source
        latest = self._download()
        assert latest.status_code == status.HTTP_200_OK
        assert self._bytes(latest) == second_source
        history_repo = self.project.git_repo
        first_blob = history_repo.commit(first_sha).tree / "stalagmight.stalx"
        blob_sha = first_blob.hexsha
        self.project.construct_git_history_from_project(history_repo)
        assert set(
            ProjectCommit.objects.filter(
                project=self.project, id__in=[first_sha, second_sha]
            ).values_list("id", flat=True)
        ) == {first_sha, second_sha}

        blob = self.client.get(
            reverse(
                "api:v2:project-download-blob",
                kwargs={"id": self.project.id, "hexsha": blob_sha},
            ),
            headers={"authorization": self.auth},
        )
        assert blob.status_code == status.HTTP_200_OK
        assert self._bytes(blob) == self.source
        dump = self._download(hexsha=first_sha, fileformat="dump")
        assert dump.status_code == status.HTTP_200_OK
        with zipfile.ZipFile(io.BytesIO(self._bytes(dump))) as archive:
            assert archive.read("stalagmight.stalx") == self.source

    def test_missing_source_reports_canonical_filename_at_latest_and_revision(
        self,
    ) -> None:
        repo = self.project.git_repo
        baseline_sha = repo.head.commit.hexsha
        for hexsha in (None, baseline_sha):
            response = self._download(hexsha=hexsha)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            assert isinstance(response, Response)
            assert "stalagmight.stalx" in response.data["error"]
            assert baseline_sha in response.data["error"]

    @parameterized.expand([PermissionType.USER, PermissionType.TEAM])
    def test_read_only_download_and_revoked_access(
        self, permission_type: PermissionType
    ) -> None:
        uploaded = self._upload(self.source)
        assert isinstance(uploaded, Response)
        assert uploaded.status_code == status.HTTP_200_OK, uploaded.data
        self.project.release_mutex(self.user)
        UserProjectPermission.objects.filter(
            project=self.project, target=self.user
        ).delete()
        self.set_test_project_permission(
            level=PermissionLevel.READ_ONLY, permission_type=permission_type
        )
        for hexsha in (None, str(uploaded.data["hexsha"])):
            response = self._download(hexsha=hexsha)
            assert response.status_code == status.HTTP_200_OK
            assert self._bytes(response) == self.source
        UserProjectPermission.objects.filter(
            project=self.project, target=self.user
        ).update(is_active=False)
        TeamProjectPermission.objects.filter(project=self.project).update(
            is_active=False
        )
        for hexsha in (None, str(uploaded.data["hexsha"])):
            denied = self._download(hexsha=hexsha)
            assert denied.status_code == status.HTTP_403_FORBIDDEN


class TestStalagmightDownloadAuthentication(BaseAPIProjectTestCase):
    @parameterized.expand([None, "a" * 40])
    def test_native_download_requires_authentication(self, hexsha: str | None) -> None:
        kwargs = {"id": self.project.id, "fileformat": "stalagmight"}
        route = "project-download"
        if hexsha is not None:
            route = "project-download-at-hash"
            kwargs["hexsha"] = hexsha
        response = self.client.get(reverse(f"api:v2:{route}", kwargs=kwargs))
        assert response.status_code == status.HTTP_403_FORBIDDEN
