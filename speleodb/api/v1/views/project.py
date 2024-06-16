#!/usr/bin/env python
# -*- coding: utf-8 -*-

from decimal import Decimal
from decimal import InvalidOperation as DecimalInvalidOperation

from django.core.exceptions import ValidationError
from django_countries import countries
from django_countries.fields import Country
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from speleodb.api.v1.permissions import UserHasAdminAccess
from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.permissions import UserHasWriteAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.surveys.models import Permission
from speleodb.surveys.models import Project
from speleodb.utils.api_decorators import method_permission_classes


class ProjectApiView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer
    http_method_names = ["get", "put", "delete"]
    lookup_field = "id"

    @method_permission_classes((UserHasReadAccess,))
    def get(self, request, *args, **kwargs):
        project = self.get_object()
        serializer = ProjectSerializer(project, context={"user": request.user})

        return Response(
            {
                "project": serializer.data,
                "history": project.commit_history,
            }
        )

    @method_permission_classes((UserHasWriteAccess,))
    def put(self, request, *args, **kwargs):
        try:
            serializer = ProjectSerializer(
                data=request.data, context={"user": request.user}
            )
            if serializer.is_valid():
                serializer.save()

                return Response({"data": serializer.data}, status=status.HTTP_200_OK)

            return Response(
                {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        except ValidationError as e:
            return Response(
                {"errors": e.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @method_permission_classes((UserHasAdminAccess,))
    def delete(self, request, *args, **kwargs):
        # Note: We only delete the permissions, rendering the project invisible to the
        # users. After 30 days, the project gets automatically deleted by a cronjob.
        # This is done to protect users from malicious/erronous project deletion.

        project = self.get_object()
        for perm in project.get_all_permissions():
            perm.deactivate(request.user)

        return Response({"id": str(project.id)})


class CreateProjectApiView(GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        try:
            serializer = ProjectSerializer(
                data=request.data, context={"user": request.user}
            )
            if serializer.is_valid():
                proj = serializer.save()
                Permission.objects.create(
                    project=proj, user=request.user, level=Permission.Level.ADMIN
                )

                return Response(
                    {"data": serializer.data}, status=status.HTTP_201_CREATED
                )

            return Response(
                {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        except ValidationError as e:
            return Response(
                {"errors": e.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ProjectListApiView(GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        usr_projects = [perm.project for perm in request.user.get_all_permissions()]

        usr_projects = sorted(
            usr_projects, key=lambda proj: proj.modified_date, reverse=True
        )

        serializer = ProjectSerializer(
            usr_projects, many=True, context={"user": request.user}
        )

        return Response(serializer.data)
