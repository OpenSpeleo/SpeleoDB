# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import UserHasAdminAccess
from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.serializers import UserPermissionListSerializer
from speleodb.api.v1.serializers import UserPermissionSerializer
from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import Project
from speleodb.surveys.models import UserPermission
from speleodb.users.models import User
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.exceptions import BadRequestError
from speleodb.utils.exceptions import NotAuthorizedError
from speleodb.utils.exceptions import UserNotActiveError
from speleodb.utils.exceptions import UserNotFoundError
from speleodb.utils.exceptions import ValueNotFoundError
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response


class ProjectUserPermissionListView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [UserHasReadAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        project = self.get_object()
        user = self.get_user()
        permissions = project.user_permissions

        project_serializer = ProjectSerializer(project, context={"user": user})
        permission_serializer = UserPermissionListSerializer(permissions)  # type: ignore[arg-type]

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permissions": permission_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class ProjectUserPermissionView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [UserHasAdminAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def _process_request_data(
        self, request: Request, data: dict[str, Any], skip_level: bool = False
    ) -> dict[str, Any]:
        request_user = self.get_user()
        perm_data: dict[str, Any] = {}
        for key in ["user", "level"]:
            try:
                if key == "level" and skip_level:
                    continue

                value = data[key]

                match key:
                    case "level":
                        if not isinstance(value, str) or value.upper() not in [
                            name for _, name in PermissionLevel.choices
                        ]:
                            raise BadRequestError(
                                f"Invalid value received for `{key}`: `{value}`"
                            )

                        try:
                            perm_data[key] = PermissionLevel.from_str(value.upper())
                        except AttributeError as e:
                            raise ValueNotFoundError(
                                f"The user permission level: `{value.upper()}` does "
                                "not exist."
                            ) from e

                    case "user":
                        try:
                            user = User.objects.get(email=value)
                        except ObjectDoesNotExist as e:
                            raise UserNotFoundError(
                                f"The user: `{value}` does not exist."
                            ) from e

                        if request_user == user:
                            # This by default make no sense because you need to be
                            # project admin to create permission. So you obviously can't
                            # create permission for yourself. Added just as safety and
                            # logical consistency.
                            raise NotAuthorizedError(
                                "A user can not edit their own permission"
                            )

                        if not user.is_active:
                            raise UserNotActiveError(
                                f"The user: `{value}` is inactive."
                            )

                        perm_data["user"] = user

                    case _:
                        raise ValueNotFoundError(f"Unknown key: {key}")

            except KeyError as e:
                raise ValueNotFoundError(
                    f"Attribute: `{key}` is missing. {data}"
                ) from e

        return perm_data

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        project = self.get_object()
        user = self.get_user()

        perm_data = self._process_request_data(request=request, data=request.data)

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
        project_serializer = ProjectSerializer(project, context={"user": user})

        # Refresh the `modified_date` field
        project.save()

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permission": permission_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        project = self.get_object()
        user = self.get_user()

        perm_data = self._process_request_data(request=request, data=request.data)

        # Can't edit your own permission
        if user == perm_data["user"]:
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
        project_serializer = ProjectSerializer(project, context={"user": user})

        # Refresh the `modified_date` field
        project.save()

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permission": permission_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        project = self.get_object()
        user = self.get_user()

        perm_data = self._process_request_data(
            request=request, data=request.data, skip_level=True
        )

        # Can't edit your own permission
        if user == perm_data["user"]:
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

        permission.deactivate(deactivated_by=user)
        project_serializer = ProjectSerializer(project, context={"user": user})

        # Refresh the `modified_date` field
        project.save()

        return SuccessResponse(
            {
                "project": project_serializer.data,
            },
            status=status.HTTP_204_NO_CONTENT,
        )
