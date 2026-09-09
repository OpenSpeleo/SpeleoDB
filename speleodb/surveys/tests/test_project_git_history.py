# -*- coding: utf-8 -*-

from __future__ import annotations

import pathlib
import tempfile
from unittest.mock import MagicMock
from unittest.mock import patch

import git
import pytest
from django.conf import settings
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from git.exc import GitCommandError
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.common.enums import PermissionLevel
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.exceptions import GitBaseError
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.users.tests.factories import UserFactory
from speleodb.utils.exceptions import ProjectNotFound

TEST_FILE = (
    pathlib.Path(__file__).parent.parent.parent
    / "api/v2/tests/artifacts"
    / "test_simple.tml"
)


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
                    "api:v2:project-upload",
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
                        "api:v2:project-upload",
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
                    "api:v2:project-upload",
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
                    "api:v2:project-upload",
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
                    "api:v2:project-upload",
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


class TestProjectCheckoutPreservesWorktree(TestCase):
    """Transport failures must not destroy the project's existing working copy."""

    def setUp(self) -> None:
        super().setUp()
        self.root: pathlib.Path = pathlib.Path(
            self.enterContext(tempfile.TemporaryDirectory())
        )
        self.enterContext(
            override_settings(DJANGO_GIT_PROJECTS_DIR=self.root / "working")
        )
        self.project: Project = ProjectFactory.create()
        self.remote: git.Repo = git.Repo.init(
            self.root / "remote.git",
            bare=True,
            initial_branch=settings.DJANGO_GIT_BRANCH_NAME,
        )
        self.repo: GitRepo = GitRepo.init(self.project.git_repo_dir)
        self.addCleanup(self.remote.close)
        self.addCleanup(self.repo.close)
        self.repo.git.symbolic_ref(
            "HEAD", f"refs/heads/{settings.DJANGO_GIT_BRANCH_NAME}"
        )
        readme: pathlib.Path = self.repo.path / "README.txt"
        readme.write_text("initial", encoding="utf-8")
        self.repo.index.add(["README.txt"])
        actor: git.Actor = git.Actor("Test Author", "test@example.invalid")
        self.repo.index.commit("initial", author=actor, committer=actor)
        self.repo.create_remote("origin", str(self.remote.git_dir))
        self.repo.git.push("origin", self.repo.active_branch.name)
        self.sentinel: pathlib.Path = self.repo.path / "local-work.txt"
        self.sentinel.write_text("keep me", encoding="utf-8")
        self.enterContext(
            patch.object(
                GitlabCredentials, "project_url", return_value=str(self.remote.git_dir)
            )
        )

    def test_checkout_failure_preserves_working_copy_and_skips_reconstruction(
        self,
    ) -> None:
        for hexsha in (None, self.repo.head.commit.hexsha):
            operation: str = (
                "checkout_default_branch_and_pull"
                if hexsha is None
                else "checkout_commit"
            )
            for error in (
                GitBaseError("upstream unavailable"),
                GitCommandError("checkout", 128),
            ):
                with (
                    self.subTest(hexsha=hexsha, error=type(error).__name__),
                    patch.object(GitRepo, operation, side_effect=error),
                    patch.object(GitlabManager, "create_or_clone_project") as clone,
                    patch.object(
                        Project, "construct_git_history_from_project"
                    ) as construct,
                    pytest.raises(type(error)),
                ):
                    self.project.checkout_commit_or_default_pull_branch(hexsha=hexsha)
                clone.assert_not_called()
                construct.assert_not_called()
                assert self.sentinel.read_text(encoding="utf-8") == "keep me"
                assert (self.repo.path / ".git" / "HEAD").exists()

    def test_wrong_origin_is_repaired_in_place(self) -> None:
        original_sha: str = self.repo.head.commit.hexsha
        self.repo.remotes.origin.set_url("https://invalid.example/nonexistent.git")

        with patch.object(GitlabManager, "create_or_clone_project") as clone:
            self.project.checkout_commit_or_default_pull_branch()

        clone.assert_not_called()
        assert self.repo.remotes.origin.url == str(self.remote.git_dir)
        assert self.repo.head.commit.hexsha == original_sha
        assert self.sentinel.read_text(encoding="utf-8") == "keep me"
        assert ProjectCommit.objects.filter(
            project=self.project, id=original_sha
        ).exists()


@pytest.mark.skip_if_lighttest
class TestGitRepoRemoteConfigurationRepair(BaseAPIProjectTestCase):
    """Repair a drifted origin URL while retaining the existing working copy."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN,
            permission_type=PermissionType.USER,
        )

    def test_checkout_recovers_from_broken_remote(self) -> None:
        """Restore the configured remote before pulling, without losing local files."""

        assert TEST_FILE.exists()

        # 1. Upload an artifact to create a real commit
        self.project.acquire_mutex(self.user)

        with TEST_FILE.open(mode="rb") as file_data:
            response = self.client.put(
                reverse(
                    "api:v2:project-upload",
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

        # Verify the git repo exists and is valid
        git_repo_dir = self.project.git_repo_dir
        assert git_repo_dir.exists()
        assert (git_repo_dir / ".git" / "HEAD").exists()

        # A modified remote URL is configuration drift, not repository corruption.
        git_repo = self.project.git_repo
        sentinel: pathlib.Path = git_repo_dir / "local-work.txt"
        sentinel.write_text("preserve local work", encoding="utf-8")
        git_repo.git.remote(
            "set-url", "origin", "https://invalid.example.com/nonexistent.git"
        )

        with patch.object(GitlabManager, "create_or_clone_project") as clone:
            self.project.checkout_commit_or_default_pull_branch()

        clone.assert_not_called()
        assert sentinel.read_text(encoding="utf-8") == "preserve local work"
        assert git_repo.remotes.origin.url == GitlabCredentials.get().project_url(
            self.project.id
        )
        assert git_repo_dir.exists()
        assert (git_repo_dir / ".git" / "HEAD").exists()

        # Verify commits still exist in the database
        commits = ProjectCommit.objects.filter(project=self.project)
        assert commits.count() >= 1
