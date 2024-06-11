#!/usr/bin/env python
# -*- coding: utf-8 -*-

from decimal import Decimal
from decimal import InvalidOperation as DecimalInvalidOperation

from django_countries import countries
from django_countries.fields import Country
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
    http_method_names = ["get", "put"]
    lookup_field = "id"

    def _get(self, request, *args, **kwargs):
        project = self.get_object()
        serializer = ProjectSerializer(project, context={"user": request.user})

        return {
            "project": serializer.data,
            "history": project.commit_history,
        }

    def _put(self, request, *args, **kwargs):
        project = self.get_object()

        modified_attrs = {}
        for key in ["name", "description", "country", "latitude", "longitude"]:
            try:
                new_value = request.data[key]

                if key == "country":
                    if new_value not in countries:
                        return Response(
                            {"error": f"The country: `{new_value}` does not exist."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    new_value = Country(code=new_value)

                elif key in ["latitude", "longitude"]:
                    try:
                        new_value = Decimal.from_float(float(new_value))
                    except (DecimalInvalidOperation, TypeError, ValueError):
                        return Response(
                            {"error": f"The value: `{key}={new_value}` is invalid."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

            except KeyError:
                return Response(
                    {"error": f"Attribute: `{key}` is missing"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if new_value == getattr(project, key):
                continue

            modified_attrs[key] = new_value

        if modified_attrs:
            for key, value in modified_attrs.items():
                setattr(project, key, value)
            project.save(update_fields=modified_attrs)

        serializer = ProjectSerializer(project, context={"user": request.user})
        return {
            "project": serializer.data,
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
