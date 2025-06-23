# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import permissions

from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import Project
from speleodb.users.models.team import SurveyTeam
from speleodb.users.models.team import SurveyTeamMembership

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView

    from speleodb.utils.requests import AuthenticatedDRFRequest


class BaseProjectAccessLevel(permissions.BasePermission):
    MIN_ACCESS_LEVEL: int

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_authenticated)

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


class UserHasAdminAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.ADMIN


class UserHasWriteAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.READ_AND_WRITE


class UserHasReadAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LEVEL = PermissionLevel.READ_ONLY


class BaseTeamAccessLevel(permissions.BasePermission):
    MIN_ACCESS_LEVEL: int

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(
        self,
        request: AuthenticatedDRFRequest,  # type: ignore[override]
        view: APIView,
        obj: SurveyTeam,
    ) -> bool:
        try:
            membership = obj.get_membership(user=request.user)
            return (
                membership.role.value >= self.MIN_ACCESS_LEVEL and membership.is_active
            )
        except ObjectDoesNotExist:
            return False


class UserHasLeaderAccess(BaseTeamAccessLevel):
    MIN_ACCESS_LEVEL = SurveyTeamMembership.Role.LEADER


class UserHasMemberAccess(BaseTeamAccessLevel):
    MIN_ACCESS_LEVEL = SurveyTeamMembership.Role.MEMBER


class IsReadOnly(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return request.method in permissions.SAFE_METHODS


class IsObjectCreation(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return request.method == "POST"


class UserOwnsProjectMutex(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_authenticated)

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
