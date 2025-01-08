#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import TYPE_CHECKING

from django.contrib.auth.models import update_last_login
from rest_framework import permissions
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.generics import GenericAPIView
from rest_framework.settings import api_settings
from rest_framework.throttling import UserRateThrottle

from speleodb.api.v1.serializers import AuthTokenSerializer
from speleodb.api.v1.serializers import PasswordChangeSerializer
from speleodb.api.v1.serializers import UserSerializer
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import NoWrapResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from speleodb.users.models import User


class UserInfo(GenericAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return SuccessResponse(
            self.get_serializer(request.user).data, status=status.HTTP_200_OK
        )

    def put(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(serializer.data, status=status.HTTP_200_OK)

        return ErrorResponse(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    def patch(self, request, *args, **kwargs):
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
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return ErrorResponse(
                status=status.HTTP_401_UNAUTHORIZED,
                data={"error": "Not authenticated"},
            )

        user: User = request.user

        token, _ = Token.objects.get_or_create(user=user)
        update_last_login(None, user=user)

        return NoWrapResponse({"token": token.key})

    def _fetch_token(self, request, refresh_token=False, *args, **kwargs):
        user: User = request.user

        if not user.is_authenticated:
            serializer = self.get_serializer(data=request.data)

            if not serializer.is_valid():
                return ErrorResponse(
                    {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
                )
            user: User = serializer.validated_data["user"]

        if refresh_token:
            # delete to recreate a fresh token
            Token.objects.filter(user=user).delete()

        token, created = Token.objects.get_or_create(user=user)
        update_last_login(None, user=user)

        return NoWrapResponse(
            {"token": token.key},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        return self._fetch_token(request, *args, refresh_token=False, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self._fetch_token(request, *args, refresh_token=True, **kwargs)

    def put(self, request, *args, **kwargs):
        return self._fetch_token(request, *args, refresh_token=True, **kwargs)


class PasswordChangeThrottle(UserRateThrottle):
    rate = "3/h"


class UserPasswordChangeView(GenericAPIView):
    serializer_class = PasswordChangeSerializer
    throttle_classes = [PasswordChangeThrottle]
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, *args, **kwargs):
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


class ReleaseAllUserLocksView(GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        user: User = request.user

        active_mutexes = user.active_mutexes
        for mutex in active_mutexes:
            mutex.release_mutex(user=user, comment="Batch unlocking")

        return SuccessResponse(
            "All locks have been released", status=status.HTTP_204_NO_CONTENT
        )
