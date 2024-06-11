#!/usr/bin/env python
# -*- coding: utf-8 -*-

from decimal import Decimal
from decimal import InvalidOperation as DecimalInvalidOperation

from django.core.exceptions import ValidationError
from django_countries import countries
from django_countries.fields import Country
from rest_framework import permissions
from rest_framework import status
from rest_framework.response import Response

from speleodb.api.v1.permissions import UserHasAdminAccess
from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.serializers import PermissionListSerializer
from speleodb.api.v1.serializers import PermissionSerializer
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.surveys.models import Permission
from speleodb.surveys.models import Project
from speleodb.utils.view_cls import CustomAPIView


class ProjectPermissionListView(CustomAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasReadAccess]
    serializer_class = ProjectSerializer
    http_method_names = ["get"]
    lookup_field = "id"

    def _get(self, request, *args, **kwargs):
        project = self.get_object()
        permissions = project.get_all_permissions()

        project_serializer = ProjectSerializer(project, context={"user": request.user})
        permission_serializer = PermissionListSerializer(permissions)

        return {
            "project": project_serializer.data,
            "permissions": permission_serializer.data,
        }


class ProjectPermissionView(CustomAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasAdminAccess]
    serializer_class = ProjectSerializer
    http_method_names = ["post", "put", "delete"]
    lookup_field = "id"
