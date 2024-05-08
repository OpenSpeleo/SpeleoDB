#!/usr/bin/env python
# -*- coding: utf-8 -*-

from rest_framework import permissions
from speleodb.surveys.model_files.permission import Permission
from speleodb.surveys.models import Project

from django.core.exceptions import ObjectDoesNotExist


class BaseProjectAccessLevel(permissions.BasePermission):
    MIN_ACCESS_LELEL = None

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True

        try:
            return obj.get_permission(user=request.user).level >= self.MIN_ACCESS_LELEL
        except ObjectDoesNotExist:
            return False


class UserHasWriteAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LELEL = Permission.Level.READ_AND_WRITE
    message = "You must have write access for this project."


class UserHasReadAccess(BaseProjectAccessLevel):
    MIN_ACCESS_LELEL = Permission.Level.READ_ONLY
    message = "You must have read access for this project."