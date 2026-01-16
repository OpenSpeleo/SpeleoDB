# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import permissions
from rest_framework.exceptions import NotAuthenticated

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Cylinder
from speleodb.gis.models import CylinderFleet
from speleodb.gis.models import CylinderFleetUserPermission
from speleodb.gis.models import CylinderInstall
from speleodb.gis.models import Experiment
from speleodb.gis.models import ExperimentRecord
from speleodb.gis.models import ExperimentUserPermission
from speleodb.gis.models import ExplorationLead
from speleodb.gis.models import GISView
from speleodb.gis.models import GPSTrack
from speleodb.gis.models import Landmark
from speleodb.gis.models import Sensor
from speleodb.gis.models import SensorFleet
from speleodb.gis.models import SensorFleetUserPermission
from speleodb.gis.models import SensorInstall
from speleodb.gis.models import Station
from speleodb.gis.models import StationLogEntry
from speleodb.gis.models import StationResource
from speleodb.gis.models import SubSurfaceStation
from speleodb.gis.models import SurfaceMonitoringNetwork
from speleodb.gis.models import SurfaceMonitoringNetworkUserPermission
from speleodb.gis.models import SurfaceStation
from speleodb.surveys.models import Project
from speleodb.users.models import SurveyTeamMembershipRole
from speleodb.utils.exceptions import NotAuthorizedError

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView

    from speleodb.users.models.team import SurveyTeam
    from speleodb.utils.requests import AuthenticatedDRFRequest

# ================ PROJECT PERMISSIONS ================ #


class BaseAccessLevel(permissions.BasePermission):
    MIN_ACCESS_LEVEL: int

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.user and request.user.is_authenticated:
            return True

        raise NotAuthenticated("Authentication credentials were not provided.")

    def _check_project_permission(
        self, request: AuthenticatedDRFRequest, project: Project
    ) -> bool:
        """Check permission on a project."""
        try:
            return (
                request.user.get_best_permission(project=project).level
                >= self.MIN_ACCESS_LEVEL
            )
        except (ObjectDoesNotExist, NotAuthorizedError):
            return False

    def has_object_permission(
        self,
        request: AuthenticatedDRFRequest,  # type: ignore[override]
        view: APIView,
        obj: Any,
    ) -> bool:
        match obj:
            # =============================================================== #
            #                           CORE MODELS                           #
            # =============================================================== #
            case Project():
                try:
                    return (
                        request.user.get_best_permission(project=obj).level
                        >= self.MIN_ACCESS_LEVEL
                    )
                except ObjectDoesNotExist, NotAuthorizedError:
                    return False

            case SurfaceMonitoringNetwork():
                try:
                    return (
                        SurfaceMonitoringNetworkUserPermission.objects.get(
                            user=request.user,
                            network=obj,
                            is_active=True,
                        ).level
                        >= self.MIN_ACCESS_LEVEL
                    )
                except ObjectDoesNotExist, NotAuthorizedError:
                    return False

            case SensorFleet():
                try:
                    return (
                        SensorFleetUserPermission.objects.get(
                            user=request.user,
                            sensor_fleet=obj,
                            is_active=True,
                        ).level
                        >= self.MIN_ACCESS_LEVEL
                    )

                except ObjectDoesNotExist:
                    return False

            case CylinderFleet():
                try:
                    return (
                        CylinderFleetUserPermission.objects.get(
                            user=request.user,
                            cylinder_fleet=obj,
                            is_active=True,
                        ).level
                        >= self.MIN_ACCESS_LEVEL
                    )
                except ObjectDoesNotExist:
                    return False

            case Experiment():
                try:
                    return (
                        ExperimentUserPermission.objects.get(
                            user=request.user,
                            experiment=obj,
                            is_active=True,
                        ).level
                        >= self.MIN_ACCESS_LEVEL
                    )
                except ObjectDoesNotExist, NotAuthorizedError:
                    return False

            # =============================================================== #
            #                        TRANSITIVE MODELS                        #
            # =============================================================== #

            # Station Models
            # -----------------------------------------------------------------

            case SubSurfaceStation():
                # Call on the `Project` underlying object
                return self.has_object_permission(
                    request,
                    view,
                    obj.project,
                )

            case SurfaceStation():
                # Call on the `SurfaceMonitoringNetwork` underlying object
                return self.has_object_permission(
                    request,
                    view,
                    obj.network,
                )

            case Station():
                # NOTE: THIS MUST BE AFTER THE POLYMORPHIC MODELS TO GUARANTEE
                #       IT DOESN'T MATCH EVERYTHING !

                # ForeignKey to polymorphic model returns base class by default
                # Call get_real_instance() to get the actual polymorphic child
                return self.has_object_permission(
                    request,
                    view,
                    obj.get_real_instance(),  # type: ignore[no-untyped-call]
                )

            case StationResource() | StationLogEntry():
                # Call on the `Station` underlying object

                # ForeignKey to polymorphic model returns base class by default
                # Call get_real_instance() to get the actual polymorphic child
                return self.has_object_permission(
                    request,
                    view,
                    obj.station.get_real_instance(),  # type: ignore[no-untyped-call]
                )

            # SurfaceMonitoringNetwork Models
            # -----------------------------------------------------------------
            case SurfaceMonitoringNetworkUserPermission():
                # Call on the `SurfaceMonitoringNetwork` underlying object
                return self.has_object_permission(request, view, obj.network)

            # Experiment Models
            # -----------------------------------------------------------------
            case ExperimentRecord():
                # Call on the `Experiment` underlying object
                return self.has_object_permission(
                    request,
                    view,
                    obj.experiment,
                )

            # SensorFleet Models
            # -----------------------------------------------------------------
            case Sensor():
                # Call on the `SensorFleet` underlying object
                return self.has_object_permission(request, view, obj.fleet)

            case Cylinder():
                # Call on the `CylinderFleet` underlying object
                return self.has_object_permission(request, view, obj.fleet)

            case SensorFleetUserPermission():
                # Call on the `SensorFleet` underlying object
                return self.has_object_permission(request, view, obj.sensor_fleet)

            case CylinderFleetUserPermission():
                # Call on the `CylinderFleet` underlying object
                return self.has_object_permission(request, view, obj.cylinder_fleet)

            # SensorFleet & Station Models
            # -----------------------------------------------------------------
            case SensorInstall():
                # Call on the `SensorFleet` and `Station` underlying objects
                station_perm = self.has_object_permission(
                    request,
                    view,
                    obj.station.get_real_instance(),  # type: ignore[no-untyped-call]
                )

                fleet_perm = self.has_object_permission(
                    request,
                    view,
                    obj.sensor.fleet,
                )

                return station_perm and fleet_perm

            case CylinderInstall():
                # Call on the `CylinderFleet` underlying object
                return self.has_object_permission(request, view, obj.cylinder.fleet)

            # ExplorationLead Models
            # -----------------------------------------------------------------

            case ExplorationLead():
                # Call on the `SensorFleet` underlying object
                return self.has_object_permission(request, view, obj.project)

            # =============================================================== #
            #                              ERROR                              #
            # =============================================================== #
            case _:
                raise TypeError(f"Unknown `type` received: {type(obj)}.")


class SDB_WebViewerAccess(BaseAccessLevel):  # noqa: N801
    MIN_ACCESS_LEVEL = PermissionLevel.WEB_VIEWER


class SDB_ReadAccess(BaseAccessLevel):  # noqa: N801
    MIN_ACCESS_LEVEL = PermissionLevel.READ_ONLY


class SDB_WriteAccess(BaseAccessLevel):  # noqa: N801
    MIN_ACCESS_LEVEL = PermissionLevel.READ_AND_WRITE


class SDB_AdminAccess(BaseAccessLevel):  # noqa: N801
    MIN_ACCESS_LEVEL = PermissionLevel.ADMIN


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
        mutex = obj.active_mutex

        if mutex is None:
            return False

        return mutex.user.id == request.user.id


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


# ================ Landmark ================ #


class LandmarkOwnershipPermission(permissions.BasePermission):
    """
    Permission class specifically for Landmark ownership.
    - Users can only see/modify their own Landmarks
    - No sharing or public access to Landmarks
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.user and request.user.is_authenticated:
            return True

        raise NotAuthenticated("Authentication credentials were not provided.")

    def has_object_permission(
        self,
        request: AuthenticatedDRFRequest,  # type: ignore[override]
        view: APIView,
        obj: Landmark,
    ) -> bool:
        """Users can only access Landmarks they created."""
        # Check if the object has a created_by field and if it matches the user
        if not isinstance(obj, Landmark):
            raise TypeError(f"Expected a `Landmark` object, got {type(obj)}")

        return obj.user == request.user


# =============== GPS Track =============== #


class GPSTrackOwnershipPermission(permissions.BasePermission):
    """
    Permission class specifically for GPSTrack ownership.
    - Users can only see/modify their own GPSTrack.
    - No sharing or public access to GPSTrack
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.user and request.user.is_authenticated:
            return True

        raise NotAuthenticated("Authentication credentials were not provided.")

    def has_object_permission(
        self,
        request: AuthenticatedDRFRequest,  # type: ignore[override]
        view: APIView,
        obj: GPSTrack,
    ) -> bool:
        """Users can only access Landmarks they created."""
        # Check if the object has a created_by field and if it matches the user
        if not isinstance(obj, GPSTrack):
            raise TypeError(f"Expected a `GPSTrack` object, got {type(obj)}")

        return obj.user == request.user


# ================ GISView ================ #


class GISViewOwnershipPermission(permissions.BasePermission):
    """
    Permission class specifically for Landmark ownership.
    - Users can only see/modify their own Landmarks
    - No sharing or public access to Landmarks
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
        """Users can only access Landmarks they created."""
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
