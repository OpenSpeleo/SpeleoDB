"""Every valid revision, including an empty initial commit, has a ZIP download."""

from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path

import git
from django.http import StreamingHttpResponse
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.common.enums import PermissionLevel


class TestEmptyDumpDownload(BaseAPIProjectTestCase):
    def test_empty_revision_downloads_valid_zip(self) -> None:
        self.set_test_project_permission(
            level=PermissionLevel.READ_ONLY, permission_type=PermissionType.USER
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            override_settings(DJANGO_GIT_PROJECTS_DIR=directory),
            git.Repo.init(Path(directory) / str(self.project.pk)) as repository,
        ):
            actor = git.Actor("Survey author", "author@example.invalid")
            commit = repository.index.commit(
                "Empty initial revision", author=actor, committer=actor
            )
            response = self.client.get(
                reverse(
                    "api:v2:project-download-at-hash",
                    kwargs={
                        "id": self.project.pk,
                        "fileformat": "dump",
                        "hexsha": commit.hexsha,
                    },
                ),
                headers={"authorization": self.auth},
            )
            assert response.status_code == status.HTTP_200_OK
            assert isinstance(response, StreamingHttpResponse)
            assert not response.is_async
            try:
                payload = b"".join(response.streaming_content)
            finally:
                response.close()
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                assert archive.namelist() == []
