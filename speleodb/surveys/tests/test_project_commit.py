# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from speleodb.api.v1.tests.factories import ProjectCommitFactory
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.surveys.models import ProjectCommit
from speleodb.users.tests.factories import UserFactory


class TestProjectCommitModel(TestCase):
    """Test suite for ProjectCommit model basic functionality."""

    def setUp(self) -> None:
        self.user = UserFactory.create()
        self.project = ProjectFactory.create(created_by=self.user.email)

    def test_create_commit_with_all_fields(self) -> None:
        """Test creating a Project Commit with all required fields."""
        commit_oid = "a" * 40  # Valid 40-char hex SHA
        commit = ProjectCommitFactory.create(
            id=commit_oid,
            project=self.project,
            author_name="Test Author",
            author_email="test@example.com",
            message="Test commit message",
            tree=[
                {
                    "mode": "100644",
                    "type": "blob",
                    "object": "b" * 40,
                    "path": "test.txt",
                }
            ],
        )

        assert commit.id == commit_oid
        assert commit.project == self.project
        assert commit.author_name == "Test Author"
        assert commit.author_email == "test@example.com"
        assert commit.message == "Test commit message"
        assert len(commit.tree) == 1

    def test_sha_validation_valid(self) -> None:
        """Test that valid SHA-1 hashes are accepted."""
        valid_shas = [
            "a" * 40,  # All lowercase
            "A" * 40,  # All uppercase (should be normalized)
            "0123456789abcdef0123456789abcdef01234567",  # Mixed
            "ffffffffffffffffffffffffffffffffffffffff",  # Max value
        ]

        for sha in valid_shas:
            commit = ProjectCommitFactory.create(
                id=sha,
                project=self.project,
            )

            # SHA should be stored as-is (case preserved by CharField)
            assert len(commit.id) == 40  # noqa: PLR2004

    def test_sha_validation_invalid(self) -> None:
        """Test that invalid SHA-1 hashes are rejected."""
        invalid_shas = [
            "g" * 40,  # Invalid hex character
            "a" * 39,  # Too short
            "a" * 41,  # Too long
            "",  # Empty
            "not-a-valid-sha",  # Invalid format
        ]

        for sha in invalid_shas:
            commit = ProjectCommit(
                id=sha,
                project=self.project,
                author_name="Author",
                author_email="author@test.com",
                message="Message",
                authored_date=timezone.now(),
            )
            with pytest.raises(ValidationError):
                commit.full_clean()  # Trigger validation

    def test_unique_oid_constraint(self) -> None:
        """Test that OID must be unique."""
        oid = "a" * 40
        ProjectCommitFactory.create(
            id=oid,
            project=self.project,
        )

        # Attempting to create another commit with same OID should fail
        with pytest.raises(IntegrityError):
            ProjectCommitFactory.create(
                id=oid,
                project=self.project,
            )

    def test_parent_child_relationships(self) -> None:
        """Test JSONField parent relationships."""
        # Create root commit
        root_commit = ProjectCommitFactory.create(
            id="a" * 40,
            project=self.project,
        )

        # Create child commit
        child_commit = ProjectCommitFactory.create(
            id="b" * 40,
            project=self.project,
            parent_ids=[root_commit.id],
        )

        # Verify relationship
        assert len(child_commit.parent_ids) == 1
        assert child_commit.parent_ids[0] == root_commit.id

    def test_multiple_parents(self) -> None:
        """Test commit with multiple parents (merge commit)."""
        parent1 = ProjectCommitFactory.create(
            id="a" * 40,
            project=self.project,
        )

        parent2 = ProjectCommitFactory.create(
            id="b" * 40,
            project=self.project,
        )

        merge_commit = ProjectCommitFactory.create(
            id="c" * 40,
            project=self.project,
            parent_ids=[parent1.id, parent2.id],
        )

        assert len(merge_commit.parent_ids) == 2  # noqa: PLR2004
        assert set(merge_commit.parent_ids) == {parent1.id, parent2.id}

    def test_is_root_property_true(self) -> None:
        """Test is_root property returns True for root commits."""
        root_commit = ProjectCommitFactory.create(
            id="a" * 40,
            project=self.project,
        )

        assert root_commit.is_root is True

    def test_is_root_property_false(self) -> None:
        """Test is_root property returns False for non-root commits."""
        parent_commit = ProjectCommitFactory.create(
            id="a" * 40,
            project=self.project,
        )

        child_commit = ProjectCommitFactory.create(
            id="b" * 40,
            project=self.project,
            parent_ids=[parent_commit.id],
        )

        assert child_commit.is_root is False

    def test_string_representations(self) -> None:
        """Test __str__ and __repr__ methods."""
        commit = ProjectCommitFactory.create(
            id="abcd1234" + "0" * 32,
            project=self.project,
            author_name="John Doe",
            author_email="john@example.com",
            message="Test message",
        )

        # Test __str__ includes short SHA and datetime
        str_repr = str(commit)
        assert "abcd1234" in str_repr
        assert "Commit" in str_repr

        # Test __repr__ includes author info
        repr_str = repr(commit)
        assert "John Doe" in repr_str
        assert "john@example.com" in repr_str
        assert "Test message" in repr_str

    def test_ordering_by_authored_date_descending(self) -> None:
        """Test that commits are ordered by -authored_date (most recent first)."""
        old_time = timezone.now() - datetime.timedelta(days=2)
        mid_time = timezone.now() - datetime.timedelta(days=1)
        new_time = timezone.now()

        commit_old = ProjectCommitFactory.create(
            id="a" * 40,
            project=self.project,
            authored_date=old_time,
        )

        commit_new = ProjectCommitFactory.create(
            id="b" * 40,
            project=self.project,
            authored_date=new_time,
        )

        commit_mid = ProjectCommitFactory.create(
            id="c" * 40,
            project=self.project,
            authored_date=mid_time,
        )

        # Query all commits - should be ordered newest first
        commits = list(ProjectCommit.objects.filter(project=self.project))
        assert commits[0] == commit_new
        assert commits[1] == commit_mid
        assert commits[2] == commit_old

    def test_cascade_deletion_with_project(self) -> None:
        """Test that commits are deleted when project is deleted."""
        commit = ProjectCommitFactory.create(
            id="a" * 40,
            project=self.project,
        )

        commit_id = commit.id
        assert ProjectCommit.objects.filter(id=commit_id).exists()

        # Delete project
        self.project.delete()

        # Commit should also be deleted
        assert not ProjectCommit.objects.filter(id=commit_id).exists()

    def test_tree_json_field_storage(self) -> None:
        """Test that tree field stores and retrieves JSON correctly."""
        tree_data = [
            {
                "mode": "100644",
                "type": "blob",
                "object": "a" * 40,
                "path": "file1.txt",
            },
            {
                "mode": "100644",
                "type": "blob",
                "object": "b" * 40,
                "path": "dir/file2.txt",
            },
        ]

        commit = ProjectCommitFactory.create(
            id="a" * 40,
            project=self.project,
            tree=tree_data,
        )

        # Refresh from DB
        commit.refresh_from_db()

        assert commit.tree == tree_data
        assert len(commit.tree) == 2  # noqa: PLR2004
        assert commit.tree[0]["path"] == "file1.txt"
        assert commit.tree[1]["path"] == "dir/file2.txt"

    def test_empty_tree_field(self) -> None:
        """Test that tree field can be empty."""
        commit = ProjectCommitFactory.create(
            id="a" * 40,
            project=self.project,
            tree={},  # Empty tree
        )

        assert commit.tree == {}
