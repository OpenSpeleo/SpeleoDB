#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Any

from django.contrib.auth.models import update_last_login
from rest_framework import permissions
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.throttling import UserRateThrottle

from speleodb.api.v1.serializers import AuthTokenSerializer
from speleodb.api.v1.serializers import PasswordChangeSerializer
from speleodb.api.v1.serializers import UserSerializer
from speleodb.users.models import User
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import NoWrapResponse
from speleodb.utils.response import SuccessResponse


class AuthenticatedRequest(Request):
    user: User


class UserInfo(GenericAPIView[User]):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: AuthenticatedRequest, *args: Any, **kwargs: Any) -> Response:
        return SuccessResponse(
            self.get_serializer(request.user).data, status=status.HTTP_200_OK
        )

    def put(self, request: AuthenticatedRequest, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_200_OK)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def patch(
        self, request: AuthenticatedRequest, *args: Any, **kwargs: Any
    ) -> Response:
        serializer = self.get_serializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_200_OK)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class UserAuthTokenView(ObtainAuthToken):
    serializer_class = AuthTokenSerializer
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES  # type: ignore[assignment]

    def get(self, request: AuthenticatedRequest, *args: Any, **kwargs: Any) -> Response:
        if not request.user.is_authenticated:
            return ErrorResponse(
                status=status.HTTP_401_UNAUTHORIZED,
                data={"error": "Not authenticated"},
            )

        user = request.user

        token, _ = Token.objects.get_or_create(user=user)
        update_last_login(None, user=user)  # type: ignore[arg-type]

        return NoWrapResponse({"token": token.key})

    def _fetch_token(
        self, request: AuthenticatedRequest, refresh_token: bool
    ) -> Response:
        if not request.user.is_authenticated:
            serializer = self.get_serializer(data=request.data)

            if not serializer.is_valid():
                return ErrorResponse(
                    {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
                )
            user: User = serializer.validated_data["user"]

        else:
            user = request.user

        if refresh_token:
            # delete to recreate a fresh token
            Token.objects.filter(user=user).delete()

        token, created = Token.objects.get_or_create(user=user)
        update_last_login(None, user=user)  # type: ignore[arg-type]

        return NoWrapResponse(
            {"token": token.key},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def post(
        self,
        request: AuthenticatedRequest,  # type: ignore[override]
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        return self._fetch_token(request, refresh_token=False)

    def patch(
        self, request: AuthenticatedRequest, *args: Any, **kwargs: Any
    ) -> Response:
        return self._fetch_token(request, refresh_token=True)

    def put(self, request: AuthenticatedRequest, *args: Any, **kwargs: Any) -> Response:
        return self._fetch_token(request, refresh_token=True)


class PasswordChangeThrottle(UserRateThrottle):
    rate = "3/h"


class UserPasswordChangeView(GenericAPIView[User]):
    serializer_class = PasswordChangeSerializer
    throttle_classes = [PasswordChangeThrottle]
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request: AuthenticatedRequest, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(
            data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return NoWrapResponse(
                {"message": "Password changed successfully"}, status=status.HTTP_200_OK
            )

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class ReleaseAllUserLocksView(GenericAPIView[User]):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def delete(
        self, request: AuthenticatedRequest, *args: Any, **kwargs: Any
    ) -> Response:
        user = request.user

        active_mutexes = user.active_mutexes
        for mutex in active_mutexes:
            mutex.release_mutex(user=user, comment="Batch unlocking")

        return SuccessResponse(
            "All locks have been released", status=status.HTTP_204_NO_CONTENT
        )
