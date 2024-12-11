import pathlib

import pytest
from django.urls import reverse
from parameterized import parameterized
from rest_framework import status

from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.tests.base_testcase import AnyPermissionLevel
from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.utils import is_subset
from speleodb.api.v1.tests.utils import is_valid_git_sha
from speleodb.surveys.models import Format
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.utils.test_utils import named_product

BASE_DIR = pathlib.Path(__file__).parent / "artifacts"
TEST_FILES = [
    BASE_DIR / "test_simple.tml",
    BASE_DIR / "test_simple.tmlu",
    # BASE_DIR / "fulford.dat",
]


class FileViewTests(BaseAPIProjectTestCase):
    @parameterized.expand(
        named_product(
            testfile=TEST_FILES,
            level=[
                UserPermission.Level.ADMIN,
                UserPermission.Level.READ_AND_WRITE,
                TeamPermission.Level.READ_AND_WRITE,
            ],
        )
    )
    def test_upload_valid_file(
        self, testfile: pathlib.Path, uploader_access_level: AnyPermissionLevel
    ):
        """
        Test file uploads with valid formats.
        """
        assert testfile.exists()

        self.set_test_project_permission(level=uploader_access_level)

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
                    "api:v1:upload_project",
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
            "content_type": "application/octet-stream",
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
                UserPermission.Level.ADMIN,
                UserPermission.Level.READ_AND_WRITE,
                TeamPermission.Level.READ_AND_WRITE,
            ],
        )
    )
    def test_upload_file_error_without_mutex(
        self, testfile: pathlib.Path, uploader_access_level: AnyPermissionLevel
    ):
        """
        Test file uploads with valid formats.
        """
        assert testfile.exists()

        self.set_test_project_permission(level=uploader_access_level)

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
                    "api:v1:upload_project",
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
                UserPermission.Level.READ_ONLY,
                TeamPermission.Level.READ_ONLY,
            ],
        )
    )
    def test_upload_error_in_readonly(
        self, testfile: pathlib.Path, uploader_access_level: AnyPermissionLevel
    ):
        """
        Test file uploads with valid formats.
        """
        assert testfile.exists()

        self.set_test_project_permission(level=uploader_access_level)

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
                    "api:v1:upload_project",
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
