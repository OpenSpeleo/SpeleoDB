#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import permissions

from speleodb.surveys.models import UserPermission
from speleodb.users.model_files.team import SurveyTeamMembership


class BaseProjectAccessLevel(permissions.BasePermission):
    MIN_ACCESS_LEVEL = None

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        try:
            return (
                obj.get_user_permission(user=request.user)._level  # noqa: SLF001
                >= self.MIN_ACCESS_LEVEL
            )
        except ObjectDoesNotExist:
            return False


class UserHasAdminAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LEVEL = UserPermission.Level.ADMIN
    message = "You must have admin access for this project."


class UserHasWriteAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LEVEL = UserPermission.Level.READ_AND_WRITE
    message = "You must have write access for this project."


class UserHasReadAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LEVEL = UserPermission.Level.READ_ONLY
    message = "You must have read access for this project."


class BaseTeamAccessLevel(permissions.BasePermission):
    MIN_ACCESS_LEVEL = None

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        try:
            return obj.get_membership(user=request.user)._role >= self.MIN_ACCESS_LEVEL  # noqa: SLF001
        except ObjectDoesNotExist:
            return False


class UserHasLeaderAccess(BaseTeamAccessLevel):
    MIN_ACCESS_LEVEL = SurveyTeamMembership.Role.LEADER
    message = "You must have leader access for this project."


class UserHasMemberAccess(BaseTeamAccessLevel):
    MIN_ACCESS_LEVEL = SurveyTeamMembership.Role.MEMBER
    message = "You must have member or leader access for this project."
