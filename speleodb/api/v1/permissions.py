#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import permissions

from speleodb.surveys.models import Project
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.users.model_files.team import SurveyTeam
from speleodb.users.model_files.team import SurveyTeamMembership


class BaseProjectAccessLevel(permissions.BasePermission):
    MIN_ACCESS_USER_LEVEL = None
    MIN_ACCESS_TEAM_LEVEL = None

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj: Project) -> bool:
        try:
            user_access = (
                obj.get_user_permission(user=request.user)._level  # noqa: SLF001
                >= self.MIN_ACCESS_USER_LEVEL
            )
        except ObjectDoesNotExist:
            user_access = False

        if user_access or self.MIN_ACCESS_TEAM_LEVEL is None:
            return user_access

        for team in request.user.teams:
            try:
                if (
                    obj.get_team_permission(team=team)._level  # noqa: SLF001
                    >= self.MIN_ACCESS_TEAM_LEVEL
                ):
                    return True
            except ObjectDoesNotExist:
                continue
        return False


class UserHasAdminAccess(BaseProjectAccessLevel):
    MIN_ACCESS_USER_LEVEL = UserPermission.Level.ADMIN


class UserHasWriteAccess(BaseProjectAccessLevel):
    MIN_ACCESS_USER_LEVEL = UserPermission.Level.READ_AND_WRITE
    MIN_ACCESS_TEAM_LEVEL = TeamPermission.Level.READ_AND_WRITE


class UserHasReadAccess(BaseProjectAccessLevel):
    MIN_ACCESS_USER_LEVEL = UserPermission.Level.READ_ONLY
    MIN_ACCESS_TEAM_LEVEL = TeamPermission.Level.READ_ONLY


class BaseTeamAccessLevel(permissions.BasePermission):
    MIN_ACCESS_LEVEL = None

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj: SurveyTeam) -> bool:
        try:
            membership = obj.get_membership(user=request.user)
            return (
                membership._role >= self.MIN_ACCESS_LEVEL  # noqa: SLF001
                and membership.is_active
            )
        except ObjectDoesNotExist:
            return False


class UserHasLeaderAccess(BaseTeamAccessLevel):
    MIN_ACCESS_LEVEL = SurveyTeamMembership.Role.LEADER


class UserHasMemberAccess(BaseTeamAccessLevel):
    MIN_ACCESS_LEVEL = SurveyTeamMembership.Role.MEMBER


class IsReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS


class UserOwnsProjectMutex(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj: Project):
        mutex = obj.active_mutex

        if mutex is None:
            return False

        return mutex.user == request.user
