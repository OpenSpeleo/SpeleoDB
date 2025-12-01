# -*- coding: utf-8 -*-

from __future__ import annotations

import pathlib
from io import StringIO
from typing import TYPE_CHECKING

import pytest
from django.core.management import call_command
from django.urls import reverse

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit

if TYPE_CHECKING:
    import uuid

BASE_DIR = (
    pathlib.Path(__file__).parent.parent.parent.parent.parent
    / "api"
    / "v1"
    / "tests"
    / "artifacts"
)
TEST_FILE = BASE_DIR / "test_simple.tml"


@pytest.mark.skip_if_lighttest
class TestPreloadGitHistory(BaseAPIProjectTestCase):
    """Test suite for preload_git_history management command."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN,
            permission_type=PermissionType.USER,
        )

    def _upload_file(
        self, project_id: str | uuid.UUID, message: str = "Commit"
    ) -> None:
        """Helper to upload a file and create a commit."""
        project = self.project if str(self.project.id) == str(project_id) else None
        if not project:
            # If it's not self.project, we might need to handle permissions or mutex
            # For simplicity, assume we are using self.project or a project the user
            # has access to
            pass

        # We need to acquire mutex for the project we are uploading to
        # But acquire_mutex is on the project instance

        project_obj = Project.objects.get(id=project_id)
        project_obj.acquire_mutex(self.user)

        with TEST_FILE.open(mode="rb") as file_data:
            self.client.put(
                reverse(
                    "api:v1:project-upload",
                    kwargs={
                        "id": project_id,
                        "fileformat": FileFormat.ARIANE_TML.label.lower(),
                    },
                ),
                {"artifact": file_data, "message": message},
                format="multipart",
                headers={"authorization": self.auth},
            )

        project_obj.release_mutex(self.user)

    def test_preload_with_commits(self) -> None:
        """Test preloading history for a project with commits."""
        assert TEST_FILE.exists()

        # 1. Create a commit
        self._upload_file(self.project.id, "User commit")

        # Verify commit exists (User commit + Initial commit)
        assert ProjectCommit.objects.filter(project=self.project).count() >= 2  # noqa: PLR2004

        # 2. Clear the database cache (delete ProjectCommit objects)
        ProjectCommit.objects.filter(project=self.project).delete()
        assert ProjectCommit.objects.filter(project=self.project).count() == 0

        # 3. Run the management command
        out = StringIO()
        call_command("preload_git_history", stdout=out)

        # 4. Verify commits are recreated
        assert ProjectCommit.objects.filter(project=self.project).count() >= 2  # noqa: PLR2004

        # Verify user commit is present
        assert ProjectCommit.objects.filter(
            project=self.project, message="User commit"
        ).exists()

    def test_preload_no_commits(self) -> None:
        """Test preloading history for a project with no user commits."""
        # Note: Projects created via factories/GitlabManager automatically get an
        # "[Automated] Project Creation" commit.

        # Run command
        out = StringIO()
        call_command("preload_git_history", stdout=out)

        # Verify at least the initial commit exists
        assert ProjectCommit.objects.filter(project=self.project).count() >= 1

        # Verify no user commits (random check)
        assert not ProjectCommit.objects.filter(
            project=self.project, message="User commit"
        ).exists()

    def test_preload_multiple_projects(self) -> None:
        """Test preloading history for multiple projects."""
        # Create a second project
        project2 = ProjectFactory.create(created_by=self.user.email)

        # Grant permission to user for project2 so we can upload

        UserProjectPermissionFactory(
            target=self.user, project=project2, level=PermissionLevel.ADMIN
        )

        # Upload to project 1
        self._upload_file(self.project.id, "Project 1 Commit")

        # Upload to project 2
        self._upload_file(project2.id, "Project 2 Commit")

        # Verify commits exist
        assert ProjectCommit.objects.filter(project=self.project).count() >= 2  # noqa: PLR2004
        assert ProjectCommit.objects.filter(project=project2).count() >= 2  # noqa: PLR2004

        # Clear DB cache
        ProjectCommit.objects.all().delete()
        assert ProjectCommit.objects.count() == 0

        # Run command
        out = StringIO()
        call_command("preload_git_history", stdout=out)

        # Verify commits recreated for both
        assert ProjectCommit.objects.filter(project=self.project).count() >= 2  # noqa: PLR2004
        assert ProjectCommit.objects.filter(project=project2).count() >= 2  # noqa: PLR2004

        assert ProjectCommit.objects.filter(
            project=self.project, message="Project 1 Commit"
        ).exists()
        assert ProjectCommit.objects.filter(
            project=project2, message="Project 2 Commit"
        ).exists()
