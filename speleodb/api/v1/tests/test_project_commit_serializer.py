# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime

from django.test import TestCase
from django.utils import timezone

from speleodb.api.v1.serializers.project_commit import ProjectCommitSerializer
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.surveys.models import ProjectCommit
from speleodb.users.tests.factories import UserFactory


class TestProjectCommitSerializer(TestCase):
    """Test suite for ProjectCommitSerializer."""

    def setUp(self) -> None:
        self.user = UserFactory.create()
        self.project = ProjectFactory.create(created_by=self.user.email)

    def test_basic_serialization(self) -> None:
        """Test basic serialization of a ProjectCommit."""
        commit = ProjectCommit.objects.create(
            oid="a" * 40,
            project=self.project,
            author_name="Test Author",
            author_email="test@example.com",
            message="Test commit message",
            datetime=timezone.now(),
            tree=[
                {
                    "mode": "100644",
                    "type": "blob",
                    "object": "b" * 40,
                    "path": "test.txt",
                }
            ],
        )

        serializer = ProjectCommitSerializer(commit)
        data = serializer.data

        # Verify all fields are present
        assert "oid" in data
        assert "parents" in data
        assert "author_name" in data
        assert "author_email" in data
        assert "message" in data
        assert "datetime" in data
        assert "tree" in data
        assert "creation_date" in data
        assert "modified_date" in data

        # Verify field values
        assert data["oid"] == "a" * 40
        assert data["author_name"] == "Test Author"
        assert data["author_email"] == "test@example.com"
        assert data["message"] == "Test commit message"
        assert len(data["tree"]) == 1

    def test_parents_as_sha_list(self) -> None:
        """Test that parents field returns list of SHA strings, not objects."""
        # Create parent commits
        parent1 = ProjectCommit.objects.create(
            oid="a" * 40,
            project=self.project,
            author_name="Author",
            author_email="author@test.com",
            message="Parent 1",
            datetime=timezone.now(),
        )

        parent2 = ProjectCommit.objects.create(
            oid="b" * 40,
            project=self.project,
            author_name="Author",
            author_email="author@test.com",
            message="Parent 2",
            datetime=timezone.now(),
        )

        parents = [parent1, parent2]

        # Create child commit
        child = ProjectCommit.objects.create(
            oid="c" * 40,
            project=self.project,
            author_name="Author",
            author_email="author@test.com",
            message="Child",
            datetime=timezone.now(),
            parents=[parent.oid for parent in parents],
        )

        # Serialize
        serializer = ProjectCommitSerializer(child)
        data = serializer.data

        # Verify parents is a list of strings
        assert isinstance(data["parents"], list)
        assert len(data["parents"]) == len(parents)
        assert all(isinstance(p, str) for p in data["parents"])
        assert set(data["parents"]) == {"a" * 40, "b" * 40}

    def test_empty_parents_for_root_commit(self) -> None:
        """Test that root commit has empty parents list."""
        root_commit = ProjectCommit.objects.create(
            oid="a" * 40,
            project=self.project,
            author_name="Author",
            author_email="author@test.com",
            message="Root commit",
            datetime=timezone.now(),
        )

        serializer = ProjectCommitSerializer(root_commit)
        data = serializer.data

        assert data["parents"] == []

    def test_all_fields_read_only(self) -> None:
        """Test that all fields are read-only."""
        serializer = ProjectCommitSerializer()

        # All fields in Meta should be read_only
        assert serializer.Meta.read_only_fields == serializer.Meta.fields

    def test_consistent_serialization(self) -> None:
        """Test that serializing the same commit twice produces identical output."""
        commit = ProjectCommit.objects.create(
            oid="a" * 40,
            project=self.project,
            author_name="Author",
            author_email="author@test.com",
            message="Test",
            datetime=timezone.now(),
            tree=[
                {"mode": "100644", "type": "blob", "object": "b" * 40, "path": "f.txt"}
            ],
        )

        serializer1 = ProjectCommitSerializer(commit)
        data1 = serializer1.data

        serializer2 = ProjectCommitSerializer(commit)
        data2 = serializer2.data

        assert data1 == data2

    def test_many_commits_serialization(self) -> None:
        """Test serializing a queryset of multiple commits."""
        commits = []
        n_commits = 3
        for i in range(n_commits):
            commit = ProjectCommit.objects.create(
                oid=f"{i:02d}" + "0" * 38,
                project=self.project,
                author_name=f"Author {i}",
                author_email=f"author{i}@test.com",
                message=f"Commit {i}",
                datetime=timezone.now() - datetime.timedelta(days=i),
            )
            commits.append(commit)

        serializer = ProjectCommitSerializer(commits, many=True)
        data = serializer.data

        assert len(data) == n_commits
        assert all("oid" in item for item in data)
        assert all("parents" in item for item in data)

    def test_tree_field_serialization(self) -> None:
        """Test that tree field with complex structure is serialized correctly."""
        tree_data = [
            {
                "mode": "100644",
                "type": "blob",
                "object": "a" * 40,
                "path": "file1.txt",
            },
            {
                "mode": "100755",
                "type": "blob",
                "object": "b" * 40,
                "path": "scripts/run.sh",
            },
            {
                "mode": "100644",
                "type": "blob",
                "object": "c" * 40,
                "path": "data/nested/deep/file.json",
            },
        ]

        commit = ProjectCommit.objects.create(
            oid="a" * 40,
            project=self.project,
            author_name="Author",
            author_email="author@test.com",
            message="Test",
            datetime=timezone.now(),
            tree=tree_data,
        )

        serializer = ProjectCommitSerializer(commit)
        data = serializer.data

        assert data["tree"] == tree_data
