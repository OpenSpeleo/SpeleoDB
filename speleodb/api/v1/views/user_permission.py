#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from speleodb.api.v1.permissions import UserHasAdminAccess
from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.serializers import UserPermissionListSerializer
from speleodb.api.v1.serializers import UserPermissionSerializer
from speleodb.surveys.models import Project
from speleodb.surveys.models import UserPermission
from speleodb.users.models import User
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse


class ProjectUserPermissionListView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [UserHasReadAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def get(self, request, *args, **kwargs):
        project: Project = self.get_object()
        permissions = project.user_permissions

        project_serializer = ProjectSerializer(project, context={"user": request.user})
        permission_serializer = UserPermissionListSerializer(permissions)

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permissions": permission_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class ProjectUserPermissionView(GenericAPIView):
    queryset = Project.objects.all()
    permission_classes = [UserHasAdminAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def _process_request_data(self, data, skip_level=False):
        perm_data = {}
        for key in ["user", "level"]:
            try:
                if key == "level" and skip_level:
                    continue

                value = data[key]

                if key == "level":
                    if not isinstance(value, str) or value.upper() not in [
                        name for _, name in UserPermission.Level.choices
                    ]:
                        return ErrorResponse(
                            {"error": f"Invalid value received for `{key}`: `{value}`"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    perm_data[key] = getattr(UserPermission.Level, value.upper())

                elif key in "user":
                    try:
                        perm_data[key] = User.objects.get(email=value)
                    except ObjectDoesNotExist:
                        return ErrorResponse(
                            {"error": f"The user: `{value}` does not exist."},
                            status=status.HTTP_404_NOT_FOUND,
                        )
                    if not perm_data[key].is_active:
                        return ErrorResponse(
                            {"error": f"The user: `{value}` is inactive."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

            except KeyError:
                return ErrorResponse(
                    {"error": f"Attribute: `{key}` is missing"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return perm_data

    def post(self, request, *args, **kwargs):
        project: Project = self.get_object()

        perm_data = self._process_request_data(data=request.data)

        # An Error occured
        if isinstance(perm_data, Response):
            return perm_data

        # Can't edit your own permission
        if request.user == perm_data["user"]:
            # This by default make no sense because you need to be project admin
            # to create permission. So you obviously can't create permission for
            # yourself. Added just as safety and logical consistency.
            return ErrorResponse(
                {"error": ("A user can not edit their own permission")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        permission, created = UserPermission.objects.get_or_create(
            project=project, target=perm_data["user"]
        )

        if not created and permission.is_active:
            return ErrorResponse(
                {
                    "error": (
                        f"A permission for this user: `{perm_data['user']}` "
                        "already exist."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        permission.reactivate(level=perm_data["level"])

        permission_serializer = UserPermissionSerializer(permission)
        project_serializer = ProjectSerializer(project, context={"user": request.user})

        # Refresh the `modified_date` field
        project.save()

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permission": permission_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, *args, **kwargs):
        project: Project = self.get_object()

        perm_data = self._process_request_data(data=request.data)

        # An Error occured
        if isinstance(perm_data, Response):
            return perm_data

        # Can't edit your own permission
        if request.user == perm_data["user"]:
            return ErrorResponse(
                {"error": ("A user can not edit their own permission")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            permission = UserPermission.objects.get(
                project=project, target=perm_data["user"]
            )
        except ObjectDoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        f"A permission for this user: `{perm_data['user']}` "
                        "does not exist."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if not permission.is_active:
            return ErrorResponse(
                {
                    "error": (
                        f"The permission for this user: `{perm_data['user']}` "
                        "is inactive. Recreate the permission."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        permission.level = perm_data["level"]
        permission.save()

        permission_serializer = UserPermissionSerializer(permission)
        project_serializer = ProjectSerializer(project, context={"user": request.user})

        # Refresh the `modified_date` field
        project.save()

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permission": permission_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, *args, **kwargs):
        project: Project = self.get_object()

        perm_data = self._process_request_data(data=request.data, skip_level=True)

        # An Error occured
        if isinstance(perm_data, Response):
            return perm_data

        # Can't edit your own permission
        if request.user == perm_data["user"]:
            return ErrorResponse(
                {"error": ("A user can not edit their own permission")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            permission = UserPermission.objects.get(
                project=project, target=perm_data["user"]
            )
        except ObjectDoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        f"A permission for this user: `{perm_data['user']}` "
                        "does not exist."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        permission.deactivate(deactivated_by=request.user)
        project_serializer = ProjectSerializer(project, context={"user": request.user})

        # Refresh the `modified_date` field
        project.save()

        return SuccessResponse(
            {
                "project": project_serializer.data,
            },
            status=status.HTTP_204_NO_CONTENT,
        )
