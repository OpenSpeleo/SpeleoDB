"""Tests for Landmark Collection models."""

from __future__ import annotations

import pytest
from django.db import IntegrityError
from django.db import transaction

from speleodb.common.enums import ColorPalette
from speleodb.common.enums import PermissionLevel
from speleodb.gis.landmark_collections import PERSONAL_LANDMARK_COLLECTION_COLOR
from speleodb.gis.landmark_collections import get_or_create_personal_landmark_collection
from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import LandmarkCollectionUserPermission
from speleodb.users.models import User


@pytest.mark.django_db
class TestLandmarkCollectionModel:
    def test_collection_generates_gis_token(self) -> None:
        user = User.objects.create_user(email="creator@example.com")
        collection = LandmarkCollection.objects.create(
            name="Benchmarks",
            created_by=user.email,
        )

        assert collection.id is not None
        assert len(collection.gis_token) == 40  # noqa: PLR2004
        assert ColorPalette.is_valid_hex(collection.color)
        assert str(collection) == "Landmark Collection: Benchmarks"
        assert collection.collection_type == LandmarkCollection.CollectionType.SHARED

    def test_refresh_gis_token_changes_token(self) -> None:
        collection = LandmarkCollection.objects.create(
            name="Benchmarks",
            created_by="creator@example.com",
        )
        old_token = collection.gis_token

        collection.refresh_gis_token()

        assert collection.gis_token != old_token
        assert len(collection.gis_token) == 40  # noqa: PLR2004

    def test_personal_collection_helper_creates_single_admin_collection(
        self,
    ) -> None:
        user = User.objects.create_user(email="creator@example.com")

        first = get_or_create_personal_landmark_collection(user=user)
        second = get_or_create_personal_landmark_collection(user=user)

        assert first == second
        assert first.name == "Personal Landmarks"
        assert first.color == PERSONAL_LANDMARK_COLLECTION_COLOR
        assert first.collection_type == LandmarkCollection.CollectionType.PERSONAL
        assert first.personal_owner == user
        permission = LandmarkCollectionUserPermission.objects.get(
            collection=first,
            user=user,
        )
        assert permission.is_active
        assert permission.level == PermissionLevel.ADMIN
        assert (
            LandmarkCollection.objects.filter(
                collection_type=LandmarkCollection.CollectionType.PERSONAL,
                personal_owner=user,
            ).count()
            == 1
        )

    def test_personal_collection_constraints(self) -> None:
        user = User.objects.create_user(email="creator@example.com")
        LandmarkCollection.objects.create(
            name="Personal",
            collection_type=LandmarkCollection.CollectionType.PERSONAL,
            personal_owner=user,
            created_by=user.email,
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            LandmarkCollection.objects.create(
                name="Duplicate Personal",
                collection_type=LandmarkCollection.CollectionType.PERSONAL,
                personal_owner=user,
                created_by=user.email,
            )

        with pytest.raises(IntegrityError), transaction.atomic():
            LandmarkCollection.objects.create(
                name="Broken Personal",
                collection_type=LandmarkCollection.CollectionType.PERSONAL,
                created_by=user.email,
            )

        with pytest.raises(IntegrityError), transaction.atomic():
            LandmarkCollection.objects.create(
                name="Broken Shared",
                personal_owner=user,
                created_by=user.email,
            )

    def test_landmark_collection_hard_delete_removes_member_landmarks(self) -> None:
        user = User.objects.create_user(email="creator@example.com")
        collection = LandmarkCollection.objects.create(
            name="Benchmarks",
            created_by=user.email,
        )
        landmark = Landmark.objects.create(
            name="Entrance",
            latitude=45.0,
            longitude=-122.0,
            created_by=user.email,
            collection=collection,
        )

        collection.delete()

        assert not Landmark.objects.filter(id=landmark.id).exists()

    def test_landmark_coordinate_uniqueness_is_scoped_to_collection(
        self,
    ) -> None:
        user = User.objects.create_user(email="creator@example.com")
        collection = LandmarkCollection.objects.create(
            name="Benchmarks",
            created_by=user.email,
        )
        other_collection = LandmarkCollection.objects.create(
            name="Other Benchmarks",
            created_by=user.email,
        )
        personal_collection = get_or_create_personal_landmark_collection(user=user)
        personal_landmark = Landmark.objects.create(
            name="Personal",
            latitude=45,
            longitude=-122,
            created_by=user.email,
            collection=personal_collection,
        )

        first_collection_landmark = Landmark.objects.create(
            name="Collection",
            latitude=45,
            longitude=-122,
            created_by=user.email,
            collection=collection,
        )
        second_collection_landmark = Landmark.objects.create(
            name="Other Collection",
            latitude=45,
            longitude=-122,
            created_by=user.email,
            collection=other_collection,
        )

        assert first_collection_landmark.collection == collection
        assert second_collection_landmark.collection == other_collection
        assert personal_landmark.collection.is_personal

        with pytest.raises(IntegrityError), transaction.atomic():
            Landmark.objects.create(
                name="Duplicate Personal",
                latitude=45,
                longitude=-122,
                created_by=user.email,
                collection=personal_collection,
            )

    def test_collection_user_permission_unique(self) -> None:
        user = User.objects.create_user(email="reader@example.com")
        collection = LandmarkCollection.objects.create(
            name="Benchmarks",
            created_by="creator@example.com",
        )
        _ = LandmarkCollectionUserPermission.objects.create(
            user=user,
            collection=collection,
            level=PermissionLevel.READ_ONLY,
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            LandmarkCollectionUserPermission.objects.create(
                user=user,
                collection=collection,
                level=PermissionLevel.READ_AND_WRITE,
            )

    def test_deactivate_and_reactivate_permission(self) -> None:
        owner = User.objects.create_user(email="owner@example.com")
        reader = User.objects.create_user(email="reader@example.com")
        collection = LandmarkCollection.objects.create(
            name="Benchmarks",
            created_by=owner.email,
        )
        permission = LandmarkCollectionUserPermission.objects.create(
            user=reader,
            collection=collection,
            level=PermissionLevel.READ_ONLY,
        )

        permission.deactivate(deactivated_by=owner)
        permission.refresh_from_db()
        assert not permission.is_active
        assert permission.deactivated_by == owner

        permission.reactivate(level=PermissionLevel.ADMIN)
        permission.refresh_from_db()
        assert permission.is_active
        assert permission.deactivated_by is None
        assert permission.level == PermissionLevel.ADMIN
