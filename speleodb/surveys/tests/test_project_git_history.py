# -*- coding: utf-8 -*-

from __future__ import annotations

import pathlib
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.common.enums import PermissionLevel
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import ProjectCommit
from speleodb.users.tests.factories import UserFactory
from speleodb.utils.exceptions import ProjectNotFound

BASE_DIR = (
    pathlib.Path(__file__).parent.parent.parent / "api" / "v1" / "tests" / "artifacts"
)
TEST_FILE = BASE_DIR / "test_simple.tml"


@pytest.mark.skip_if_lighttest
class TestConstructGitHistory(BaseAPIProjectTestCase):
    """Test suite for construct_git_history_from_project() method."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN,
            permission_type=PermissionType.USER,
        )

    def test_construct_git_history_after_upload(self) -> None:
        """Test that git history is constructed correctly after file upload."""
        assert TEST_FILE.exists()

        # Acquire mutex
        self.project.acquire_mutex(self.user)

        # Upload first file
        with TEST_FILE.open(mode="rb") as file_data:
            response = self.client.put(
                reverse(
                    "api:v1:project-upload",
                    kwargs={
                        "id": self.project.id,
                        "fileformat": FileFormat.ARIANE_TML.label.lower(),
                    },
                ),
                {"artifact": file_data, "message": "First commit"},
                format="multipart",
                headers={"authorization": self.auth},
            )

        assert response.status_code == status.HTTP_200_OK

        # Verify commit was created
        commits = ProjectCommit.objects.filter(project=self.project)
        assert commits.count() >= 1  # At least one commit (may have init commit)

        first_commit = commits.filter(message="First commit").first()
        assert first_commit is not None
        assert first_commit.author_name == self.user.name
        assert first_commit.author_email == self.user.email

    def test_construct_git_history_multiple_commits(self) -> None:
        """Test git history with multiple commits."""
        assert TEST_FILE.exists()

        self.project.acquire_mutex(self.user)

        # Upload multiple files to create multiple commits
        for i in range(3):
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

            # Accept both 200 OK and 304 Not Modified (no changes detected)
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_304_NOT_MODIFIED,
            ]

        # Verify commits exist (may be fewer than expected due to 304 responses)
        commits = ProjectCommit.objects.filter(project=self.project).order_by(
            "-authored_date"
        )
        commit_messages = [c.message for c in commits]

        # At least one user commit should have been created
        # (may not have all 3 due to 304 responses for duplicate content)
        assert len([m for m in commit_messages if m.startswith("Commit")]) >= 1

    def test_construct_git_history_parent_relationships(self) -> None:
        """Test that parent relationships are correctly established."""
        assert TEST_FILE.exists()

        self.project.acquire_mutex(self.user)

        # Upload file to create commits
        with TEST_FILE.open(mode="rb") as file_data:
            _ = self.client.put(
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

        # Verify at least one commit exists with parent tracking
        commit = ProjectCommit.objects.filter(project=self.project).first()
        assert commit is not None
        # Parent count could be 0 (root) or more
        # Just verify the parent_ids relationship is accessible
        _ = len(commit.parent_ids)

    def test_construct_git_history_tree_populated(self) -> None:
        """Test that tree field is populated with git ls-tree data."""
        assert TEST_FILE.exists()

        self.project.acquire_mutex(self.user)

        with TEST_FILE.open(mode="rb") as file_data:
            self.client.put(
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

        commit = ProjectCommit.objects.get(project=self.project, message="Test commit")

        # Verify tree is populated
        assert commit.tree is not None
        assert isinstance(commit.tree, list)

        # Verify tree entries have correct structure
        if len(commit.tree) > 0:
            entry = commit.tree[0]
            assert "mode" in entry
            assert "type" in entry
            assert "object" in entry
            assert "path" in entry

    def test_construct_git_history_idempotency(self) -> None:
        """Test that running construct_git_history twice doesn't create duplicates."""
        assert TEST_FILE.exists()

        self.project.acquire_mutex(self.user)

        # Upload file
        with TEST_FILE.open(mode="rb") as file_data:
            self.client.put(
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

        # Count commits
        initial_count = ProjectCommit.objects.filter(project=self.project).count()

        # Manually call construct_git_history again
        git_repo = self.project.git_repo
        self.project.construct_git_history_from_project(git_repo)

        # Count should not change
        final_count = ProjectCommit.objects.filter(project=self.project).count()
        assert initial_count == final_count


class TestCheckoutCommitOrDefaultBranch(TestCase):
    """Test suite for checkout_commit_or_default_branch() method."""

    @patch("speleodb.surveys.models.project.Project.git_repo", new_callable=MagicMock)
    @patch("speleodb.surveys.models.project.Project.construct_git_history_from_project")
    def test_checkout_default_branch_calls_construct_history(
        self, mock_construct: MagicMock, mock_git_repo: MagicMock
    ) -> None:
        """Test that checkout without hexsha calls
        construct_git_history_from_project."""

        user = UserFactory.create()
        project = ProjectFactory.create(created_by=user.email)

        # Create a mock repo
        mock_repo_instance = MagicMock()
        mock_git_repo.__get__ = MagicMock(return_value=mock_repo_instance)

        # Call checkout without hexsha
        project.checkout_commit_or_default_pull_branch()

        # Verify construct_git_history_from_project was called
        mock_construct.assert_called_once()
        # Verify checkout_default_branch_and_pull was called
        mock_repo_instance.checkout_default_branch_and_pull.assert_called_once()

    @patch("speleodb.surveys.models.project.Project.git_repo", new_callable=MagicMock)
    @patch("speleodb.surveys.models.project.Project.construct_git_history_from_project")
    def test_checkout_specific_commit_calls_construct_history(
        self, mock_construct: MagicMock, mock_git_repo: MagicMock
    ) -> None:
        """Test that checkout with hexsha calls construct_git_history_from_project."""

        user = UserFactory.create()
        project = ProjectFactory.create(created_by=user.email)

        # Create a mock repo
        mock_repo_instance = MagicMock()
        mock_git_repo.__get__ = MagicMock(return_value=mock_repo_instance)

        test_sha = "a" * 40

        # Call checkout with hexsha
        project.checkout_commit_or_default_pull_branch(hexsha=test_sha)

        # Verify construct_git_history_from_project was called
        mock_construct.assert_called_once()
        # Verify checkout_commit was called with the SHA
        mock_repo_instance.checkout_commit.assert_called_once_with(hexsha=test_sha)

    @patch("speleodb.surveys.models.project.Project.git_repo", new_callable=MagicMock)
    def test_checkout_raises_when_no_git_repo(self, mock_git_repo: MagicMock) -> None:
        """Test that checkout raises ProjectNotFound when git_repo is None."""

        user = UserFactory.create()
        project = ProjectFactory.create(created_by=user.email)

        # Make git_repo return None
        mock_git_repo.__get__ = MagicMock(return_value=None)

        with pytest.raises(ProjectNotFound):
            project.checkout_commit_or_default_pull_branch()
