# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import permissions
from rest_framework.exceptions import NotAuthenticated

from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import Project
from speleodb.surveys.models import Station
from speleodb.surveys.models import StationResource
from speleodb.surveys.models.point_of_interest import PointOfInterest
from speleodb.users.models import SurveyTeamMembershipRole

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView

    from speleodb.users.models.team import SurveyTeam
    from speleodb.utils.requests import AuthenticatedDRFRequest


class BaseProjectAccessLevel(permissions.BasePermission):
    MIN_ACCESS_LEVEL: int

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.user and request.user.is_authenticated:
            return True

        raise NotAuthenticated("Authentication credentials were not provided.")

    def has_object_permission(
        self,
        request: AuthenticatedDRFRequest,  # type: ignore[override]
        view: APIView,
        obj: Project,
    ) -> bool:
        try:
            user_access = (
                obj.get_user_permission(user=request.user).level
                >= self.MIN_ACCESS_LEVEL
            )
        except ObjectDoesNotExist:
            user_access = False

        if user_access or self.MIN_ACCESS_LEVEL is None:
            return user_access

        for team in request.user.teams:
            try:
                if obj.get_team_permission(team=team).level >= self.MIN_ACCESS_LEVEL:
                    return True
            except ObjectDoesNotExist:
                continue
        return False


class BaseStationAccessLevel(permissions.BasePermission):
    """Base permission class for Station objects that checks permissions on the
    station's project."""

    MIN_ACCESS_LEVEL: int

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.user and request.user.is_authenticated:
            return True

        raise NotAuthenticated("Authentication credentials were not provided.")

    def has_object_permission(
        self,
        request: AuthenticatedDRFRequest,  # type: ignore[override]
        view: APIView,
        obj: Project | Station | StationResource,
    ) -> bool:
        # Get the project from the object
        project: Project
        match obj:
            case Project():
                # Try station.project for StationResource objects
                project = obj

            case Station():
                # Try station.project for StationResource objects
                project = obj.project

            case StationResource():
                project = obj.station.project

            case _:
                raise TypeError(
                    f"Unknown `type` received: {type(obj)}. "
                    "Expected: Station | StationResource"
                )

        try:
            return (
                project.get_best_permission(user=request.user).level
                >= self.MIN_ACCESS_LEVEL
            )

        except ObjectDoesNotExist:
            return False


class UserHasAdminAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.ADMIN


class UserHasWriteAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.READ_AND_WRITE


class UserHasReadAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.READ_ONLY


class UserHasWebViewerAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.WEB_VIEWER


# Station-specific permission classes
class StationUserHasAdminAccess(BaseStationAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.ADMIN


class StationUserHasWriteAccess(BaseStationAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.READ_AND_WRITE


class StationUserHasReadAccess(BaseStationAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.READ_ONLY


class StationUserHasWebViewerAccess(BaseStationAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.WEB_VIEWER


class BaseTeamAccessLevel(permissions.BasePermission):
    MIN_ACCESS_LEVEL: int

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.user and request.user.is_authenticated:
            return True

        raise NotAuthenticated("Authentication credentials were not provided.")

    def has_object_permission(
        self,
        request: AuthenticatedDRFRequest,  # type: ignore[override]
        view: APIView,
        obj: SurveyTeam,
    ) -> bool:
        try:
            membership = obj.get_membership(user=request.user)
            return membership.role >= self.MIN_ACCESS_LEVEL and membership.is_active
        except ObjectDoesNotExist:
            return False


class UserHasLeaderAccess(BaseTeamAccessLevel):
    MIN_ACCESS_LEVEL = SurveyTeamMembershipRole.LEADER


class UserHasMemberAccess(BaseTeamAccessLevel):
    MIN_ACCESS_LEVEL = SurveyTeamMembershipRole.MEMBER


class IsReadOnly(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.user and request.user.is_authenticated:
            return request.method in permissions.SAFE_METHODS

        raise NotAuthenticated("Authentication credentials were not provided.")


class IsObjectCreation(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.user and request.user.is_authenticated:
            return request.method == "POST"

        raise NotAuthenticated("Authentication credentials were not provided.")


class IsObjectEdition(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.user and request.user.is_authenticated:
            return request.method in ["PATCH", "PUT"]

        raise NotAuthenticated("Authentication credentials were not provided.")


class IsObjectDeletion(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.user and request.user.is_authenticated:
            return request.method in ["DELETE"]

        raise NotAuthenticated("Authentication credentials were not provided.")


class UserOwnsProjectMutex(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.user and request.user.is_authenticated:
            return True

        raise NotAuthenticated("Authentication credentials were not provided.")

    def has_object_permission(
        self,
        request: AuthenticatedDRFRequest,  # type: ignore[override]
        view: APIView,
        obj: Project,
    ) -> bool:
        mutex = obj.active_mutex

        if mutex is None:
            return False

        return mutex.user == request.user


class POIOwnershipPermission(permissions.BasePermission):
    """
    Permission class specifically for POI ownership.
    - Users can only see/modify their own POIs
    - No sharing or public access to POIs
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.user and request.user.is_authenticated:
            return True

        raise NotAuthenticated("Authentication credentials were not provided.")

    def has_object_permission(
        self,
        request: AuthenticatedDRFRequest,  # type: ignore[override]
        view: APIView,
        obj: PointOfInterest,
    ) -> bool:
        """Users can only access POIs they created."""
        # Check if the object has a created_by field and if it matches the user
        if not isinstance(obj, PointOfInterest):
            raise TypeError(f"Expected a `PointOfInterest` object, got {type(obj)}")
        return obj.created_by == request.user
