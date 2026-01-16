# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.permissions import SDB_AdminAccess
from speleodb.api.v1.permissions import SDB_ReadAccess
from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.serializers import ProjectUserPermissionSerializer
from speleodb.common.enums import PermissionLevel
from speleodb.surveys.models import Project
from speleodb.surveys.models import UserProjectPermission
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


class ProjectUserPermissionListApiView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [SDB_ReadAccess]
    serializer_class = ProjectSerializer
    lookup_field = "id"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        project = self.get_object()
        user = self.get_user()
        permissions = project.user_permissions

        project_serializer = ProjectSerializer(project, context={"user": user})
        permission_serializer = ProjectUserPermissionSerializer(permissions, many=True)

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permissions": permission_serializer.data,
            }
        )


class ProjectUserPermissionSpecificApiView(GenericAPIView[Project], SDBAPIViewMixin):
    queryset = Project.objects.all()
    permission_classes = [SDB_AdminAccess]
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

        target_user: User = perm_data["user"]
        permission, created = UserProjectPermission.objects.get_or_create(
            project=project,
            target=target_user,
        )

        if not created:
            if permission.is_active:
                return ErrorResponse(
                    {
                        "error": (
                            f"A permission for this user: `{target_user}` "
                            "already exist."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Reactivate permission
            permission.reactivate(level=perm_data["level"])

        else:
            # Now assign the role. Couldn't do it during object creation because
            # of the use of `get_or_create`
            permission.level = perm_data["level"]

        permission.save()

        permission_serializer = ProjectUserPermissionSerializer(permission)
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

        target_user: User = perm_data["user"]
        try:
            permission = UserProjectPermission.objects.get(
                project=project,
                target=target_user,
                is_active=True,
            )

        except ObjectDoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        f"A permission for this user: `{target_user}` does not exist."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        permission.level = perm_data["level"]
        permission.save()

        permission_serializer = ProjectUserPermissionSerializer(permission)
        project_serializer = ProjectSerializer(project, context={"user": user})

        # Refresh the `modified_date` field
        project.save()

        return SuccessResponse(
            {
                "project": project_serializer.data,
                "permission": permission_serializer.data,
            }
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

        target_user: User = perm_data["user"]
        try:
            permission = UserProjectPermission.objects.get(
                project=project,
                target=target_user,
                is_active=True,
            )

        except ObjectDoesNotExist:
            return ErrorResponse(
                {
                    "error": (
                        f"A permission for this user: `{target_user}` does not exist."
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
            status=status.HTTP_200_OK,
        )
