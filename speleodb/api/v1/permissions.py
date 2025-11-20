# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import permissions
from rest_framework.exceptions import NotAuthenticated

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Experiment
from speleodb.gis.models import ExperimentRecord
from speleodb.gis.models import ExperimentUserPermission
from speleodb.gis.models import GISView
from speleodb.gis.models import LogEntry
from speleodb.gis.models import PointOfInterest
from speleodb.gis.models import Station
from speleodb.gis.models import StationResource
from speleodb.surveys.models import Project
from speleodb.users.models import SurveyTeamMembershipRole
from speleodb.utils.exceptions import NotAuthorizedError

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView

    from speleodb.users.models.team import SurveyTeam
    from speleodb.utils.requests import AuthenticatedDRFRequest

# ================ PROJECT PERMISSIONS ================ #


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
            return (
                request.user.get_best_permission(project=obj).level
                >= self.MIN_ACCESS_LEVEL
            )
        except NotAuthorizedError:
            return False


class ProjectUserHasAdminAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.ADMIN


class ProjectUserHasWriteAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.READ_AND_WRITE


class ProjectUserHasReadAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.READ_ONLY


class ProjectUserHasWebViewerAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.WEB_VIEWER


# ================ Mutex ================ #


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
        mutex = obj.active_mutex()

        if mutex is None:
            return False

        return mutex.user.id == request.user.id


# ================ STATION PERMISSIONS ================ #


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
        obj: Project | Station | StationResource | LogEntry,
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

            case StationResource() | LogEntry():
                project = obj.station.project

            case _:
                raise TypeError(
                    f"Unknown `type` received: {type(obj)}. "
                    "Expected: Station | StationResource"
                )

        try:
            return (
                request.user.get_best_permission(project=project).level
                >= self.MIN_ACCESS_LEVEL
            )

        except ObjectDoesNotExist:
            return False


class StationUserHasAdminAccess(BaseStationAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.ADMIN


class StationUserHasWriteAccess(BaseStationAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.READ_AND_WRITE


class StationUserHasReadAccess(BaseStationAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.READ_ONLY


class StationUserHasWebViewerAccess(BaseStationAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.WEB_VIEWER


# ================ EXPERIMENT PERMISSIONS ================ #


class BaseExperimentAccessLevel(permissions.BasePermission):
    """Base permission class for Experiment objects that checks permissions on the
    experiment."""

    MIN_ACCESS_LEVEL: int

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.user and request.user.is_authenticated:
            return True

        raise NotAuthenticated("Authentication credentials were not provided.")

    def has_object_permission(
        self,
        request: AuthenticatedDRFRequest,  # type: ignore[override]
        view: APIView,
        obj: Experiment | ExperimentRecord,
    ) -> bool:
        experiment: Experiment
        match obj:
            case Experiment():
                # Try station.project for StationResource objects
                experiment = obj

            case ExperimentRecord():
                # Try station.project for StationResource objects
                experiment = obj.experiment

            case _:
                raise TypeError(
                    f"Unknown `type` received: {type(obj)}. Expected: Experiment"
                )

        try:
            return (
                ExperimentUserPermission.objects.get(
                    user=request.user,
                    experiment=experiment,
                    is_active=True,
                ).level
                >= self.MIN_ACCESS_LEVEL
            )

        except ObjectDoesNotExist:
            return False


class ExperimentUserHasAdminAccess(BaseExperimentAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.ADMIN


class ExperimentUserHasWriteAccess(BaseExperimentAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.READ_AND_WRITE


class ExperimentUserHasReadAccess(BaseExperimentAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.READ_ONLY


# ================ TEAM PERMISSIONS ================ #


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


# ================ POI ================ #


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

        return obj.user == request.user


# ================ GISView ================ #


class GISViewOwnershipPermission(permissions.BasePermission):
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
        obj: GISView,
    ) -> bool:
        """Users can only access POIs they created."""
        # Check if the object has a created_by field and if it matches the user
        if not isinstance(obj, GISView):
            raise TypeError(f"Expected a `GISView` object, got {type(obj)}")

        return obj.owner == request.user


# ================ MISC ================ #


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
