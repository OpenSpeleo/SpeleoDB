#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.exceptions import ValidationError
from rest_framework import permissions

from speleodb.api.v1.permissions import UserHasWriteAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.surveys.models import Project
from speleodb.utils.exceptions import NotAuthorizedError
from speleodb.utils.exceptions import ResourceBusyError
from speleodb.utils.view_cls import CustomAPIView


class ProjectAcquireApiView(CustomAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasWriteAccess]
    serializer_class = ProjectSerializer
    http_method_names = ["post"]
    lookup_field = "id"

    def _post(self, request, *args, **kwargs):
        project = self.get_object()

        try:
            project.acquire_mutex(user=request.user)

        except ValidationError as e:
            raise ResourceBusyError(e.message) from None

        except PermissionError as e:
            raise NotAuthorizedError(e) from None

        try:
            serializer = ProjectSerializer(project, context={"user": request.user})
        except Exception as e:
            project.release_mutex(user=request.user, comment=f"Error: `{e}`")
            raise

        return serializer.data


class ProjectReleaseApiView(CustomAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasWriteAccess]
    serializer_class = ProjectSerializer
    http_method_names = ["post"]
    lookup_field = "id"

    def _post(self, request, *args, **kwargs):
        project = self.get_object()
        comment = request.data.get("comment", "")
        try:
            project.release_mutex(user=request.user, comment=comment)

        except ValidationError as e:
            raise ResourceBusyError(e.message) from None

        except PermissionError as e:
            raise NotAuthorizedError(e) from None

        try:
            serializer = ProjectSerializer(project, context={"user": request.user})
        except Exception:
            project.acquire_mutex(user=request.user)
            raise

        return serializer.data
