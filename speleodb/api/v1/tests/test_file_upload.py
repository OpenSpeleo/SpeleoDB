# -*- coding: utf-8 -*-

from __future__ import annotations

import pathlib

import pytest
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.api.v1.tests.utils import is_subset
from speleodb.api.v1.tests.utils import is_valid_git_sha
from speleodb.surveys.models import Format
from speleodb.surveys.models import PermissionLevel
from speleodb.utils.test_utils import named_product

BASE_DIR = pathlib.Path(__file__).parent / "artifacts"
TEST_FILES = [
    BASE_DIR / "test_simple.tml",
    BASE_DIR / "test_simple.tmlu",
    # BASE_DIR / "fulford.dat",
]


@pytest.mark.skip_if_lighttest
class FileViewTests(BaseAPIProjectTestCase):
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
                fileformat = Format.FileFormat.ARIANE_TML
            case "TMLU":
                fileformat = Format.FileFormat.ARIANE_TMLU
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
                fileformat = Format.FileFormat.ARIANE_TML
            case "TMLU":
                fileformat = Format.FileFormat.ARIANE_TMLU
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
                fileformat = Format.FileFormat.ARIANE_TML
            case "TMLU":
                fileformat = Format.FileFormat.ARIANE_TMLU
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
