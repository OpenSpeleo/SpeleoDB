# -*- coding: utf-8 -*-

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from git.exc import GitCommandError
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import BaseProjectTestCaseMixin
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.common.enums import PermissionLevel
from speleodb.git_engine.exceptions import GitBaseError
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import ProjectCommit
from speleodb.testing.gitlab_pool import get_pool

if TYPE_CHECKING:
    from speleodb.git_engine.core import GitRepo


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
        get_pool().prepare(self.project)

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
        commit: ProjectCommit = ProjectCommit.objects.get(
            project=self.project, message="Test commit"
        )
        git_repo: GitRepo = self.project.git_repo
        assert commit.parent_ids == [
            parent.hexsha for parent in git_repo.commit(commit.id).parents
        ]
        assert len(commit.parent_ids) == 1

    def test_construct_git_history_tree_populated(self) -> None:
        """Test that tree field is populated with git ls-tree data."""
        assert TEST_FILE.exists()

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
        commit = ProjectCommit.objects.get(project=self.project, message="Test commit")

        # Verify tree is populated
        assert isinstance(commit.tree, list)
        assert commit.tree
        for entry in commit.tree:
            assert {"mode", "type", "object", "path"} <= entry.keys()

    def test_construct_git_history_idempotency(self) -> None:
        """Test that running construct_git_history twice doesn't create duplicates."""
        assert TEST_FILE.exists()

        self.project.acquire_mutex(self.user)

        # Upload file
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
        # Count commits
        initial_count = ProjectCommit.objects.filter(project=self.project).count()

        # Manually call construct_git_history again
        git_repo = self.project.git_repo
        self.project.construct_git_history_from_project(git_repo)

        # Count should not change
        final_count = ProjectCommit.objects.filter(project=self.project).count()
        assert initial_count == final_count


@pytest.mark.skip_if_lighttest
class TestCheckoutCommitOrDefaultBranch(BaseProjectTestCaseMixin):
    """Assert checkout results and SQL reconstruction using real GitLab."""

    def setUp(self) -> None:
        super().setUp()
        get_pool().prepare(self.project)
        self.repo: GitRepo = self.project.git_repo
        self.addCleanup(self.repo.close)
        self.original_sha: str = self.repo.head.commit.hexsha
        (self.repo.path / "README.txt").write_text("latest version", encoding="utf-8")
        latest_sha: str | None = self.repo.commit_and_push_project(
            "Latest revision", author_name=self.user.name, author_email=self.user.email
        )
        assert latest_sha is not None
        self.latest_sha: str = latest_sha
        assert not ProjectCommit.objects.filter(project=self.project).exists()

    def test_checkout_default_branch_constructs_history(self) -> None:
        self.repo.checkout_commit(self.original_sha)

        self.project.checkout_commit_or_default_pull_branch()

        assert self.repo.active_branch.name == settings.DJANGO_GIT_BRANCH_NAME
        assert self.repo.head.commit.hexsha == self.latest_sha
        assert set(
            ProjectCommit.objects.filter(project=self.project).values_list(
                "id", flat=True
            )
        ) == {self.original_sha, self.latest_sha}

    def test_checkout_specific_commit_constructs_history(self) -> None:
        self.project.checkout_commit_or_default_pull_branch(hexsha=self.original_sha)

        assert self.repo.head.is_detached
        assert self.repo.head.commit.hexsha == self.original_sha
        assert list(
            ProjectCommit.objects.filter(project=self.project).values_list(
                "id", flat=True
            )
        ) == [self.original_sha]

    def test_missing_commit_preserves_head_and_does_not_construct_history(self) -> None:
        missing_sha: str = "0" * 40
        # Git versions use either diagnostic for an absent tree object.
        with pytest.raises(
            GitCommandError, match=r"reference is not a tree|unable to read tree"
        ) as error:
            self.project.checkout_commit_or_default_pull_branch(hexsha=missing_sha)

        assert error.value.status == 128  # noqa: PLR2004
        assert error.value.command[-2:] == ["checkout", missing_sha]
        assert missing_sha in error.value.stderr
        assert self.repo.head.commit.hexsha == self.latest_sha
        assert not ProjectCommit.objects.filter(project=self.project).exists()

    def test_checkout_failure_preserves_working_copy_and_skips_reconstruction(
        self,
    ) -> None:
        readme: pathlib.Path = self.repo.path / "README.txt"
        readme.write_text("uncommitted changes", encoding="utf-8")
        with pytest.raises(GitCommandError, match="would be overwritten"):
            self.project.checkout_commit_or_default_pull_branch(
                hexsha=self.original_sha
            )

        assert readme.read_text(encoding="utf-8") == "uncommitted changes"
        assert self.repo.head.commit.hexsha == self.latest_sha
        assert not ProjectCommit.objects.filter(project=self.project).exists()

    def test_transport_failure_preserves_working_copy_and_skips_reconstruction(
        self,
    ) -> None:
        sentinel: pathlib.Path = self.repo.path / "local-work.txt"
        sentinel.write_text("keep me", encoding="utf-8")
        # Git itself refuses the transport through its actual repository config.
        self.repo.git.config(f"protocol.{settings.GITLAB_HTTP_PROTOCOL}.allow", "never")
        with (
            override_settings(
                DJANGO_GIT_RETRY_BASE_DELAY_SECONDS=0.01,
                DJANGO_GIT_RETRY_MAX_DELAY_SECONDS=0.02,
            ),
            pytest.raises(GitBaseError, match="not allowed"),
        ):
            self.project.checkout_commit_or_default_pull_branch()

        assert sentinel.read_text(encoding="utf-8") == "keep me"
        assert self.repo.head.commit.hexsha == self.latest_sha
        assert not ProjectCommit.objects.filter(project=self.project).exists()


@pytest.mark.skip_if_lighttest
class TestGitRepoRemoteConfigurationRepair(BaseAPIProjectTestCase):
    """Repair a drifted origin URL while retaining the existing working copy."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN,
            permission_type=PermissionType.USER,
        )
        get_pool().prepare(self.project)

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

        original_sha: str = git_repo.head.commit.hexsha
        self.project.checkout_commit_or_default_pull_branch()

        assert git_repo.head.commit.hexsha == original_sha
        assert sentinel.read_text(encoding="utf-8") == "preserve local work"
        assert git_repo.remotes.origin.url == GitlabCredentials.get().project_url(
            self.project.id
        )
        assert git_repo_dir.exists()
        assert (git_repo_dir / ".git" / "HEAD").exists()

        # Verify commits still exist in the database
        commits = ProjectCommit.objects.filter(project=self.project)
        assert commits.count() >= 1
