import pathlib
import random
import re

from django.test import TestCase
from django.urls import reverse
from parameterized import parameterized
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import SurveyTeamFactory
from speleodb.api.v1.tests.factories import TeamPermissionFactory
from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.api.v1.tests.factories import UserFactory
from speleodb.api.v1.tests.factories import UserPermissionFactory
from speleodb.surveys.models import Format
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.users.models import SurveyTeamMembership

AnyPermissionLevel = UserPermission.Level | TeamPermission.Level

BASE_DIR = pathlib.Path(__file__).parent / "artifacts"
TEST_FILES = [
    BASE_DIR / "test_simple.tml",
    BASE_DIR / "test_simple.tmlu",
    # BASE_DIR / "fulford.dat",
]


def is_valid_git_sha(hash_string: str) -> bool:
    """Check if the provided string is a valid Git SHA-1 hash."""
    pattern = r"^[0-9a-fA-F]{40}$"
    return bool(re.fullmatch(pattern, hash_string))


def is_subset(subset_dict, super_dict):
    return all(item in super_dict.items() for item in subset_dict.items())


class FileViewTests(TestCase):
    """Token authentication"""

    header_prefix = "Token "

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)

        self.user = UserFactory()
        self.token = TokenFactory(user=self.user)
        self.project = ProjectFactory()

    def set_test_permission(self, level: AnyPermissionLevel):
        if isinstance(level, UserPermission.Level):
            _ = UserPermissionFactory(
                target=self.user, level=level, project=self.project
            )

        elif isinstance(level, TeamPermission.Level):
            # Create a team for the user - assign the user to the team
            team = SurveyTeamFactory()
            _ = SurveyTeamMembership.objects.create(
                user=self.user,
                team=team,
                role=random.choice(SurveyTeamMembership.Role.values),
            )

            # Give the newly created permission to the project
            _ = TeamPermissionFactory(
                target=team,
                level=level,
                project=self.project,
            )

        else:
            raise TypeError(f"Received unexpected level type: `{type(level)}`")

    @parameterized.expand(TEST_FILES)
    def test_upload_valid_file(self, testfile: pathlib.Path):
        """
        Test file uploads with valid formats.
        """
        assert testfile.exists()

        self.set_test_permission(level=UserPermission.Level.ADMIN)

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

    @parameterized.expand(TEST_FILES)
    def test_upload_file_error_without_mutex(self, testfile: pathlib.Path):
        """
        Test file uploads with valid formats.
        """
        assert testfile.exists()

        self.set_test_permission(level=UserPermission.Level.ADMIN)

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
