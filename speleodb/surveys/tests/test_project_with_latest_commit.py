# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime

from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.users.tests.factories import UserFactory


class TestWithLatestCommitQuerySet(TestCase):
    """Test suite for with_latest_commit() QuerySet method."""

    def setUp(self) -> None:
        self.user = UserFactory.create()

    @override_settings(DEBUG=True)
    def test_with_latest_commit_prevents_n_plus_1(self) -> None:
        """Test that with_latest_commit() prevents N+1 queries."""
        # Create 10 projects with 3 commits each
        projects = []
        for i in range(10):
            project = ProjectFactory.create(created_by=self.user.email)
            projects.append(project)

            # Create 3 commits for each project
            for j in range(3):
                ProjectCommit.objects.create(
                    id=f"{i:02d}{j:02d}" + "0" * 36,
                    project=project,
                    author_name=f"Author {i}",
                    author_email=f"author{i}@test.com",
                    authored_date=timezone.now() - datetime.timedelta(days=2 - j),
                    message=f"Commit {j}",
                )

        # Test WITHOUT with_latest_commit() - this would cause N+1
        with self.assertNumQueries(1):
            # Only the project query
            list(Project.objects.all())

        # Accessing commits would require additional queries (N+1 pattern)
        # We can't easily test this without actually accessing .commits
        # but the test below shows the difference

        # Test WITH with_latest_commit() - should be constant queries
        with self.assertNumQueries(2):
            # 1 query for projects, 1 prefetch for latest commits
            projects_with = list(Project.objects.with_commits().all())  # pyright: ignore[reportAttributeAccessIssue]

            # Access the prefetched latest_commit for all projects
            for project in projects_with:
                _ = project.latest_commit  # No additional query

    def test_with_latest_commit_returns_most_recent(self) -> None:
        """Test that with_latest_commit() returns the most recent commit."""
        project = ProjectFactory.create(created_by=self.user.email)

        old_time = timezone.now() - datetime.timedelta(days=3)
        mid_time = timezone.now() - datetime.timedelta(days=2)
        new_time = timezone.now() - datetime.timedelta(days=1)

        _ = ProjectCommit.objects.create(
            id="a" * 40,
            project=project,
            author_name="Author",
            author_email="author@test.com",
            authored_date=old_time,
            message="Old commit",
        )

        _ = ProjectCommit.objects.create(
            id="b" * 40,
            project=project,
            author_name="Author",
            author_email="author@test.com",
            authored_date=mid_time,
            message="Mid commit",
        )

        commit_new = ProjectCommit.objects.create(
            id="c" * 40,
            project=project,
            author_name="Author",
            author_email="author@test.com",
            authored_date=new_time,
            message="New commit",
        )

        # Query with with_latest_commit()
        project_with_latest = Project.objects.with_commits().get(id=project.id)  # pyright: ignore[reportAttributeAccessIssue]

        # Check that latest_commit contains only the newest commit
        assert isinstance(project_with_latest.latest_commit, ProjectCommit)
        assert project_with_latest.latest_commit == commit_new

    def test_with_latest_commit_empty_when_no_commits(self) -> None:
        """Test that project with no commits has empty latest_commit."""
        project = ProjectFactory.create(created_by=self.user.email)
        # Don't create any commits

        project_with_latest = Project.objects.with_commits().get(id=project.id)  # pyright: ignore[reportAttributeAccessIssue]

        assert hasattr(project_with_latest, "latest_commit")
        assert project_with_latest.latest_commit is None

    def test_with_latest_commit_via_manager(self) -> None:
        """Test that with_latest_commit() works through the Manager."""
        project = ProjectFactory.create(created_by=self.user.email)

        commit = ProjectCommit.objects.create(
            id="a" * 40,
            project=project,
            author_name="Author",
            author_email="author@test.com",
            authored_date=timezone.now(),
            message="Commit",
        )

        # Call via Manager instead of QuerySet
        project_via_manager = Project.objects.with_commits().get(id=project.id)  # pyright: ignore[reportAttributeAccessIssue]

        assert isinstance(project_via_manager.latest_commit, ProjectCommit)
        assert project_via_manager.latest_commit == commit

    def test_with_latest_commit_multiple_projects(self) -> None:
        """Test with_latest_commit() with multiple projects having different commit
        counts."""
        # Project with no commits
        project1 = ProjectFactory.create(created_by=self.user.email)

        # Project with 1 commit
        project2 = ProjectFactory.create(created_by=self.user.email)
        commit2 = ProjectCommit.objects.create(
            id="b" * 40,
            project=project2,
            author_name="Author",
            author_email="author@test.com",
            authored_date=timezone.now(),
            message="Commit",
        )

        # Project with 5 commits
        project3 = ProjectFactory.create(created_by=self.user.email)
        for i in range(5):
            ProjectCommit.objects.create(
                id=f"c{i:02d}" + "0" * 37,
                project=project3,
                author_name="Author",
                author_email="author@test.com",
                authored_date=timezone.now() - datetime.timedelta(days=4 - i),
                message=f"Commit {i}",
            )

        # Get the latest commit for project3
        latest_commit3 = ProjectCommit.objects.filter(project=project3).order_by(
            "-authored_date"
        )[0]

        # Query all with with_latest_commit()
        projects = Project.objects.with_commits().filter(  # pyright: ignore[reportAttributeAccessIssue]
            id__in=[project1.id, project2.id, project3.id]
        )

        projects_dict = {p.id: p for p in projects}

        # Verify each project has correct latest commit
        assert projects_dict[project1.id].latest_commit is None
        assert isinstance(projects_dict[project2.id].latest_commit, ProjectCommit)
        assert projects_dict[project2.id].latest_commit == commit2
        assert isinstance(projects_dict[project3.id].latest_commit, ProjectCommit)
        assert projects_dict[project3.id].latest_commit == latest_commit3
