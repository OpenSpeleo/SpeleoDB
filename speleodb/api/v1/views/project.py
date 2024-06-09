#!/usr/bin/env python
# -*- coding: utf-8 -*-

from rest_framework import permissions
from rest_framework import status
from rest_framework.response import Response

from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.surveys.models import Permission
from speleodb.surveys.models import Project
from speleodb.utils.view_cls import CustomAPIView


class ProjectApiView(CustomAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated, UserHasReadAccess]
    serializer_class = ProjectSerializer
    http_method_names = ["get"]
    lookup_field = "id"

    def _get(self, request, *args, **kwargs):
        project = self.get_object()
        serializer = ProjectSerializer(project, context={"user": request.user})

        return {
            "project": serializer.data,
            "history": project.commit_history,
        }


class CreateProjectApiView(CustomAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer
    http_method_names = ["post"]

    def _post(self, request, *args, **kwargs):
        """
        Create the Todo with given todo data
        """
        serializer = ProjectSerializer(
            data=request.data, context={"user": request.user}
        )
        if serializer.is_valid():
            proj = serializer.save()
            Permission.objects.create(
                project=proj, user=request.user, level=Permission.Level.OWNER
            )

            return Response({"data": serializer.data}, status=status.HTTP_201_CREATED)

        return Response(
            {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class ProjectListApiView(CustomAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer
    http_method_names = ["get"]

    def _get(self, request, *args, **kwargs):
        usr_projects = [perm.project for perm in request.user.rel_permissions.all()]

        usr_projects = sorted(
            usr_projects, key=lambda proj: proj.modified_date, reverse=True
        )

        serializer = ProjectSerializer(
            usr_projects, many=True, context={"user": request.user}
        )

        return serializer.data
