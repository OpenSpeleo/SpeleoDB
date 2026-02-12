# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import io
import pathlib
import zipfile
from typing import Any
from typing import cast

import orjson
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.http import StreamingHttpResponse
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.api.v1.tests.utils import is_subset
from speleodb.api.v1.tests.utils import is_valid_git_sha
from speleodb.common.enums import PermissionLevel
from speleodb.processors._impl.compass_toml import CompassTOML
from speleodb.surveys.models import FileFormat
from speleodb.utils.test_utils import named_product

BASE_DIR = pathlib.Path(__file__).parent / "artifacts"
TEST_FILES = [
    BASE_DIR / "test_simple.tml",
    BASE_DIR / "test_simple.tmlu",
    # BASE_DIR / "fulford.dat",
]
COMPASS_TEST_FILES = [
    BASE_DIR / "sample.mak",
    BASE_DIR / "sample-1.dat",
    BASE_DIR / "sample-2.dat",
]


@pytest.mark.skip_if_lighttest
class FileViewTests(BaseAPIProjectTestCase):
    def _upload_artifacts(
        self,
        *,
        fileformat: FileFormat,
        artifact_paths: list[pathlib.Path],
        extra_artifacts: list[SimpleUploadedFile] | None = None,
        commit_message: str = "Valid commit message",
    ) -> HttpResponse:
        with contextlib.ExitStack() as stack:
            opened_files = [
                stack.enter_context(path.open(mode="rb")) for path in artifact_paths
            ]
            artifacts = [*opened_files, *(extra_artifacts or [])]

            return self.client.put(
                reverse(
                    "api:v1:project-upload",
                    kwargs={
                        "id": self.project.id,
                        "fileformat": fileformat.label.lower(),
                    },
                ),
                {"artifact": artifacts, "message": commit_message},
                format="multipart",
                headers={"authorization": f"{self.header_prefix}{self.token.key}"},
            )

    def _download_project_format(
        self, fileformat: FileFormat
    ) -> HttpResponse | StreamingHttpResponse:
        return self.client.get(
            reverse(
                "api:v1:project-download",
                kwargs={
                    "id": self.project.id,
                    "fileformat": fileformat.label.lower(),
                },
            ),
            headers={"authorization": f"{self.header_prefix}{self.token.key}"},
        )

    @staticmethod
    def _response_bytes(response: HttpResponse | StreamingHttpResponse) -> bytes:
        if isinstance(response, StreamingHttpResponse):
            stream = response.streaming_content
            if hasattr(stream, "__aiter__"):
                raise TypeError(
                    "Async streaming responses are not supported in this test"
                )
            return b"".join(response.streaming_content)  # type: ignore[arg-type]
        return bytes(response.content)

    @staticmethod
    def _response_json(
        response: HttpResponse | StreamingHttpResponse,
    ) -> dict[str, Any]:
        return cast(
            "dict[str, Any]", orjson.loads(FileViewTests._response_bytes(response))
        )

    @parameterized.expand(
        named_product(
            testfile=TEST_FILES,
            level=[
                PermissionLevel.ADMIN,
                PermissionLevel.READ_AND_WRITE,
            ],
            permission_type=[PermissionType.USER, PermissionType.TEAM],
        )
    )
    def test_upload_valid_file(
        self,
        testfile: pathlib.Path,
        uploader_access_level: PermissionLevel,
        permission_type: PermissionType,
    ) -> None:
        """
        Test file uploads with valid formats.
        """

        assert testfile.exists()

        self.set_test_project_permission(
            level=uploader_access_level,
            permission_type=permission_type,
        )

        self.project.acquire_mutex(self.user)

        fileformat = None
        match testfile.suffix.lstrip(".").upper():
            case "TML":
                fileformat = FileFormat.ARIANE_TML
            case "TMLU":
                fileformat = FileFormat.ARIANE_TMLU
            case _:
                raise ValueError(
                    f"Unknown value: `{testfile.suffix.lstrip('.').upper()}`"
                )

        commit_message = "Valid commit message"

        with testfile.open(mode="rb") as file_data:
            auth = f"{self.header_prefix}{self.token.key}"
            response = self.client.put(
                reverse(
                    "api:v1:project-upload",
                    kwargs={
                        "id": self.project.id,
                        "fileformat": fileformat.label.lower(),
                    },
                ),
                {"artifact": file_data, "message": commit_message},
                format="multipart",
                headers={"authorization": auth},
            )

        assert response.status_code == status.HTTP_200_OK, response.data

        expected_data = {
            "files": [f"project.{testfile.suffix.lstrip('.').lower()}"],
            "content_types": ["application/octet-stream"],
            "message": commit_message,
        }

        response_data = response.data["data"]
        assert is_subset(expected_data, response_data)
        assert is_valid_git_sha(response_data["hexsha"])

        # refresh all project data
        self.project.refresh_from_db()

        project_data = ProjectSerializer(self.project, context={"user": self.user}).data

        assert project_data == response_data["project"], {
            "reserialized": project_data,
            "response_data": response_data["project"],
        }

    @parameterized.expand(
        named_product(
            testfile=TEST_FILES,
            level=[
                PermissionLevel.ADMIN,
                PermissionLevel.READ_AND_WRITE,
            ],
            permission_type=[PermissionType.USER, PermissionType.TEAM],
        )
    )
    def test_upload_file_error_without_mutex(
        self,
        testfile: pathlib.Path,
        uploader_access_level: PermissionLevel,
        permission_type: PermissionType,
    ) -> None:
        """
        Test file uploads with valid formats.
        """
        assert testfile.exists()

        self.set_test_project_permission(
            level=uploader_access_level,
            permission_type=permission_type,
        )

        fileformat = None
        match testfile.suffix.lstrip(".").upper():
            case "TML":
                fileformat = FileFormat.ARIANE_TML
            case "TMLU":
                fileformat = FileFormat.ARIANE_TMLU
            case _:
                raise ValueError(
                    f"Unknown value: `{testfile.suffix.lstrip('.').upper()}`"
                )

        commit_message = "Valid commit message"

        with testfile.open(mode="rb") as file_data:
            auth = self.header_prefix + self.token.key
            response = self.client.put(
                reverse(
                    "api:v1:project-upload",
                    kwargs={
                        "id": self.project.id,
                        "fileformat": fileformat.label.lower(),
                    },
                ),
                {"artifact": file_data, "message": commit_message},
                format="multipart",
                headers={"authorization": auth},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    @parameterized.expand(
        named_product(
            testfile=TEST_FILES,
            level=[
                PermissionLevel.READ_ONLY,
            ],
            permission_type=[PermissionType.USER, PermissionType.TEAM],
        )
    )
    def test_upload_error_in_readonly(
        self,
        testfile: pathlib.Path,
        uploader_access_level: PermissionLevel,
        permission_type: PermissionType,
    ) -> None:
        """
        Test file uploads with valid formats.
        """
        assert testfile.exists()

        self.set_test_project_permission(
            level=uploader_access_level,
            permission_type=permission_type,
        )

        with pytest.raises(PermissionError):
            self.project.acquire_mutex(self.user)

        fileformat = None
        match testfile.suffix.lstrip(".").upper():
            case "TML":
                fileformat = FileFormat.ARIANE_TML
            case "TMLU":
                fileformat = FileFormat.ARIANE_TMLU
            case _:
                raise ValueError(
                    f"Unknown value: `{testfile.suffix.lstrip('.').upper()}`"
                )

        commit_message = "Valid commit message"

        with testfile.open(mode="rb") as file_data:
            auth = self.header_prefix + self.token.key
            response = self.client.put(
                reverse(
                    "api:v1:project-upload",
                    kwargs={
                        "id": self.project.id,
                        "fileformat": fileformat.label.lower(),
                    },
                ),
                {"artifact": file_data, "message": commit_message},
                format="multipart",
                headers={"authorization": auth},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    def test_upload_auto_compass_bundle_generates_compass_toml_and_assoc_zip(
        self,
    ) -> None:
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )
        self.project.acquire_mutex(self.user)

        response = self._upload_artifacts(
            fileformat=FileFormat.AUTO,
            artifact_paths=COMPASS_TEST_FILES,
        )
        response_json = self._response_json(response)
        assert response.status_code == status.HTTP_200_OK, response_json

        response_files = set(response_json["data"]["files"])
        assert {
            "sample.mak",
            "sample-1.dat",
            "sample-2.dat",
            "compass.toml",
        } <= response_files

        self.project.refresh_from_db()
        assert any(
            fmt.raw_format == FileFormat.COMPASS_ZIP for fmt in self.project.formats
        )
        assert not any(
            fmt.raw_format == FileFormat.COMPASS_MANUAL for fmt in self.project.formats
        )

        download_response = self._download_project_format(FileFormat.COMPASS_ZIP)
        assert download_response.status_code == status.HTTP_200_OK

        payload = self._response_bytes(download_response)
        with zipfile.ZipFile(io.BytesIO(payload), mode="r") as zipf:
            members = set(zipf.namelist())
            assert {
                "sample.mak",
                "sample-1.dat",
                "sample-2.dat",
                "compass.toml",
            } <= members

            cfg = CompassTOML.from_toml(io.BytesIO(zipf.read("compass.toml")))
            assert cfg.project.mak_file == "sample.mak"
            assert cfg.project.dat_files == ["sample-1.dat", "sample-2.dat"]
            assert cfg.project.plt_files == []

    def test_upload_auto_compass_bundle_includes_uploaded_plt_in_toml(self) -> None:
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )
        self.project.acquire_mutex(self.user)

        plt_file = SimpleUploadedFile(
            "sample.plt",
            b"dummy plt payload\n",
            content_type="text/plain",
        )
        response = self._upload_artifacts(
            fileformat=FileFormat.AUTO,
            artifact_paths=COMPASS_TEST_FILES,
            extra_artifacts=[plt_file],
        )
        assert response.status_code == status.HTTP_200_OK, self._response_json(response)

        download_response = self._download_project_format(FileFormat.COMPASS_ZIP)
        assert download_response.status_code == status.HTTP_200_OK

        payload = self._response_bytes(download_response)
        with zipfile.ZipFile(io.BytesIO(payload), mode="r") as zipf:
            members = set(zipf.namelist())
            assert {
                "sample.mak",
                "sample-1.dat",
                "sample-2.dat",
                "sample.plt",
                "compass.toml",
            } <= members

            cfg = CompassTOML.from_toml(io.BytesIO(zipf.read("compass.toml")))
            assert cfg.project.plt_files == ["sample.plt"]

    def test_upload_auto_compass_bundle_does_not_validate_mak_dat_references(
        self,
    ) -> None:
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )
        self.project.acquire_mutex(self.user)

        response = self._upload_artifacts(
            fileformat=FileFormat.AUTO,
            artifact_paths=[
                BASE_DIR / "sample.mak",
                BASE_DIR / "sample-1.dat",
            ],
        )
        assert response.status_code == status.HTTP_200_OK, self._response_json(response)

        download_response = self._download_project_format(FileFormat.COMPASS_ZIP)
        assert download_response.status_code == status.HTTP_200_OK

        payload = self._response_bytes(download_response)
        with zipfile.ZipFile(io.BytesIO(payload), mode="r") as zipf:
            members = set(zipf.namelist())
            assert {"sample.mak", "sample-1.dat", "compass.toml"} <= members
            assert "sample-2.dat" not in members

            cfg = CompassTOML.from_toml(io.BytesIO(zipf.read("compass.toml")))
            assert cfg.project.dat_files == ["sample-1.dat"]
