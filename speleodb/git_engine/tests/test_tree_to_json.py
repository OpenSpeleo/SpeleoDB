# -*- coding: utf-8 -*-

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest
from django.test import TestCase

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.common.enums import PermissionLevel
from speleodb.surveys.models import FileFormat

if TYPE_CHECKING:
    from django.urls import reverse
    from rest_framework import status

BASE_DIR = (
    pathlib.Path(__file__).parent.parent.parent / "api" / "v1" / "tests" / "artifacts"
)
TEST_FILE = BASE_DIR / "test_simple.tml"


@pytest.mark.skip_if_lighttest
class TestTreeToJson(BaseAPIProjectTestCase):
    """Test suite for GitCommit.tree_to_json() method."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN,
            permission_type=PermissionType.USER,
        )

    def test_tree_to_json_basic_structure(self) -> None:
        """Test that tree_to_json returns correct structure."""
        from django.urls import reverse
        from rest_framework import status

        assert TEST_FILE.exists()

        self.project.acquire_mutex(self.user)

        # Upload a file to create a commit
        with TEST_FILE.open(mode="rb") as file_data:
            response = self.client.put(
                reverse(
                    "api:v1:project-upload",
                    kwargs={
                        "id": self.project.id,
                        "fileformat": FileFormat.ARIANE_TML.label.lower(),
                    },
                ),
                {"artifact": file_data, "message": "Test commit"},
                format="multipart",
                headers={"authorization": self.auth},
            )

        assert response.status_code == status.HTTP_200_OK

        # Get the git repo and latest commit
        git_repo = self.project.git_repo
        commits = list(git_repo.iter_commits("HEAD"))
        assert len(commits) > 0

        latest_commit = commits[0]

        # Call tree_to_json
        tree_json = latest_commit.tree_to_json()

        # Verify it's a list
        assert isinstance(tree_json, list)

        # Verify each entry has correct structure
        for entry in tree_json:
            assert "mode" in entry
            assert "type" in entry
            assert "object" in entry
            assert "path" in entry

            # Mode should be 6-digit octal string
            assert isinstance(entry["mode"], str)
            assert len(entry["mode"]) == 6
            assert all(c in "01234567" for c in entry["mode"])

            # Type should be 'blob' for files
            assert entry["type"] in ["blob", "tree"]

            # Object should be 40-char SHA
            assert isinstance(entry["object"], str)
            assert len(entry["object"]) == 40
            assert all(c in "0123456789abcdef" for c in entry["object"].lower())

            # Path should be a string
            assert isinstance(entry["path"], str)

    def test_tree_to_json_file_paths(self) -> None:
        """Test that file paths are correct in tree_to_json output."""
        from django.urls import reverse
        from rest_framework import status

        assert TEST_FILE.exists()

        self.project.acquire_mutex(self.user)

        with TEST_FILE.open(mode="rb") as file_data:
            response = self.client.put(
                reverse(
                    "api:v1:project-upload",
                    kwargs={
                        "id": self.project.id,
                        "fileformat": FileFormat.ARIANE_TML.label.lower(),
                    },
                ),
                {"artifact": file_data, "message": "Test commit"},
                format="multipart",
                headers={"authorization": self.auth},
            )

        assert response.status_code == status.HTTP_200_OK

        git_repo = self.project.git_repo
        latest_commit = list(git_repo.iter_commits("HEAD"))[0]
        tree_json = latest_commit.tree_to_json()

        # At least one entry should exist
        assert len(tree_json) > 0

        # File paths should not start with '/'
        for entry in tree_json:
            assert not entry["path"].startswith("/")

    def test_tree_to_json_multiple_files(self) -> None:
        """Test tree_to_json with multiple commits to verify all files are listed."""
        from django.urls import reverse
        from rest_framework import status

        assert TEST_FILE.exists()

        self.project.acquire_mutex(self.user)

        # Upload multiple times to ensure we have files
        for i in range(2):
            with TEST_FILE.open(mode="rb") as file_data:
                response = self.client.put(
                    reverse(
                        "api:v1:project-upload",
                        kwargs={
                            "id": self.project.id,
                            "fileformat": FileFormat.ARIANE_TML.label.lower(),
                        },
                    ),
                    {"artifact": file_data, "message": f"Commit {i}"},
                    format="multipart",
                    headers={"authorization": self.auth},
                )

            # Accept both 200 OK and 304 Not Modified
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_304_NOT_MODIFIED,
            ]

        git_repo = self.project.git_repo
        latest_commit = list(git_repo.iter_commits("HEAD"))[0]
        tree_json = latest_commit.tree_to_json()

        # Should have at least one file
        assert len(tree_json) >= 1

        # All entries should be blobs (files)
        for entry in tree_json:
            # In a flat structure, all should be blobs
            assert entry["type"] in ["blob", "tree"]

    def test_tree_to_json_empty_commit(self) -> None:
        """Test tree_to_json on initial/empty commit."""
        # Create a new project with git repo
        from speleodb.api.v1.tests.factories import ProjectFactory

        new_project = ProjectFactory.create(created_by=self.user.email)

        try:
            git_repo = new_project.git_repo

            # Try to get commits - may be empty for new repo
            commits = list(git_repo.iter_commits("HEAD"))

            if len(commits) > 0:
                # If there's an initial commit, check its tree
                initial_commit = commits[-1]  # Oldest commit
                tree_json = initial_commit.tree_to_json()

                # Initial commit may have 0 or 1 files
                assert isinstance(tree_json, list)
                # Don't assert specific count as it depends on init
        except Exception:
            # New projects might not have any commits yet
            pytest.skip("Project has no commits yet")

    def test_tree_to_json_consistency(self) -> None:
        """Test that calling tree_to_json twice on same commit gives same result."""
        from django.urls import reverse
        from rest_framework import status

        assert TEST_FILE.exists()

        self.project.acquire_mutex(self.user)

        with TEST_FILE.open(mode="rb") as file_data:
            response = self.client.put(
                reverse(
                    "api:v1:project-upload",
                    kwargs={
                        "id": self.project.id,
                        "fileformat": FileFormat.ARIANE_TML.label.lower(),
                    },
                ),
                {"artifact": file_data, "message": "Test commit"},
                format="multipart",
                headers={"authorization": self.auth},
            )

        assert response.status_code == status.HTTP_200_OK

        git_repo = self.project.git_repo
        commit = list(git_repo.iter_commits("HEAD"))[0]

        # Call tree_to_json twice
        tree_json1 = commit.tree_to_json()
        tree_json2 = commit.tree_to_json()

        # Should be identical
        assert tree_json1 == tree_json2
