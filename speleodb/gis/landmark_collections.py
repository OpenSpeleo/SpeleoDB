# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import IntegrityError
from django.db import transaction

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import LandmarkCollectionUserPermission

if TYPE_CHECKING:
    from speleodb.users.models import User

PERSONAL_LANDMARK_COLLECTION_NAME = "Personal Landmarks"
PERSONAL_LANDMARK_COLLECTION_COLOR = "#ffffff"


def get_or_create_personal_landmark_collection(user: User) -> LandmarkCollection:
    """Return the user's single personal Landmark Collection.

    Fast path (collection + permission already exist and are healthy): two
    SELECTs, zero savepoints.  Slow path (first call for this user, or
    concurrent race): one savepoint for the collection create, then a
    second get_or_create for the permission.
    """
    lookup = {
        "collection_type": LandmarkCollection.CollectionType.PERSONAL,
        "personal_owner": user,
    }

    collection = LandmarkCollection.objects.filter(**lookup).first()

    if collection is None:
        defaults = {
            "name": PERSONAL_LANDMARK_COLLECTION_NAME,
            "description": "",
            "created_by": user.email,
            "is_active": True,
            "color": PERSONAL_LANDMARK_COLLECTION_COLOR,
        }
        try:
            with transaction.atomic():
                collection, _ = LandmarkCollection.objects.get_or_create(
                    **lookup,
                    defaults=defaults,
                )
        except IntegrityError:
            collection = LandmarkCollection.objects.get(**lookup)

    if not collection.is_active:
        collection.is_active = True
        collection.save(update_fields=["is_active", "modified_date"])

    permission, _ = LandmarkCollectionUserPermission.objects.get_or_create(
        user=user,
        collection=collection,
        defaults={"level": PermissionLevel.ADMIN},
    )
    if not permission.is_active or permission.level != PermissionLevel.ADMIN:
        permission.is_active = True
        permission.deactivated_by = None
        permission.level = PermissionLevel.ADMIN
        permission.save(
            update_fields=[
                "is_active",
                "deactivated_by",
                "level",
                "modified_date",
            ]
        )

    return collection
