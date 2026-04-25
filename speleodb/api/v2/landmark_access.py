# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Exists
from django.db.models import IntegerField
from django.db.models import OuterRef
from django.db.models import Q
from django.db.models import QuerySet
from django.db.models import Subquery
from django.db.models.functions import Lower

from speleodb.common.enums import PermissionLevel
from speleodb.gis.landmark_collections import get_or_create_personal_landmark_collection
from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import LandmarkCollectionUserPermission

if TYPE_CHECKING:
    from speleodb.users.models import User


def get_collection_permission_level(
    user: User,
    collection: LandmarkCollection,
) -> int | None:
    """Return the active collection permission level for a user."""
    if not collection.is_active:
        return None

    return (
        LandmarkCollectionUserPermission.objects.filter(
            user=user,
            collection=collection,
            is_active=True,
        )
        .values_list("level", flat=True)
        .first()
    )


def user_has_collection_access(
    user: User,
    collection: LandmarkCollection,
    min_level: int = PermissionLevel.READ_ONLY,
) -> bool:
    """Check whether a user has at least ``min_level`` on an active collection."""
    permission_level = get_collection_permission_level(user=user, collection=collection)
    return permission_level is not None and permission_level >= min_level


def user_has_landmark_access(
    user: User,
    landmark: Landmark,
    min_level: int = PermissionLevel.READ_ONLY,
) -> bool:
    """Check access to a Landmark via its collection permission."""
    annotated_level = getattr(landmark, "user_collection_permission_level", None)
    if annotated_level is not None:
        return landmark.collection.is_active and annotated_level >= min_level

    return user_has_collection_access(
        user=user,
        collection=landmark.collection,
        min_level=min_level,
    )


def accessible_landmark_collections_queryset(
    user: User,
) -> QuerySet[LandmarkCollection]:
    """Return active collections visible to the user with permission annotations."""
    get_or_create_personal_landmark_collection(user=user)
    permission_qs = LandmarkCollectionUserPermission.objects.filter(
        collection=OuterRef("pk"),
        user=user,
        is_active=True,
        level__gte=PermissionLevel.READ_ONLY,
    )

    return (
        LandmarkCollection.objects.filter(is_active=True)
        .filter(Exists(permission_qs))
        .annotate(
            user_permission_level=Subquery(
                permission_qs.values("level")[:1],
                output_field=IntegerField(),
            ),
        )
        .order_by("collection_type", Lower("name"))
    )


def accessible_landmarks_queryset(user: User) -> QuerySet[Landmark]:
    """Return Landmarks visible to the user through collection permissions."""
    get_or_create_personal_landmark_collection(user=user)
    permission_qs = LandmarkCollectionUserPermission.objects.filter(
        collection=OuterRef("collection_id"),
        user=user,
        is_active=True,
        level__gte=PermissionLevel.READ_ONLY,
    )

    return (
        Landmark.objects.select_related("collection")
        .annotate(
            user_collection_permission_level=Subquery(
                permission_qs.values("level")[:1],
                output_field=IntegerField(),
            ),
            user_can_read_collection=Exists(permission_qs),
        )
        .filter(Q(collection__is_active=True, user_can_read_collection=True))
        .distinct()
    )


def collection_landmarks_queryset(
    collection: LandmarkCollection,
) -> QuerySet[Landmark]:
    """Return active collection Landmarks in UI/export order."""
    return (
        Landmark.objects.filter(collection=collection, collection__is_active=True)
        .select_related("collection")
        .order_by(Lower("name"))
    )
