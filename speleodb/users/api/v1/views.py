#!/usr/bin/env python
# -*- coding: utf-8 -*-

import contextlib

from allauth.account import signals
from allauth.account.adapter import get_adapter
from allauth.account.internal.flows.password_change import logout_on_password_change
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django_countries import countries
from django_countries.fields import Country
from rest_framework import permissions
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.throttling import UserRateThrottle

from speleodb.users.api.v1.serializers import AuthTokenSerializer
from speleodb.users.api.v1.serializers import UserSerializer


class UserInfo(GenericAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(UserSerializer(request.user).data)

    def _maybe_update_email(self, request, user, new_email):
        if new_email is not None and new_email != user.email:
            validate_email(new_email)
            EmailAddress.objects.add_new_email(request, request.user, new_email)

    def put(self, request, *args, **kwargs):
        email = request.data.pop("email", None)
        try:
            self._maybe_update_email(request, user=request.user, new_email=email)
        except ValidationError:
            return Response(
                {"error": f"The email: `{email}` is invalid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            serializer = UserSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({"data": serializer.data}, status=status.HTTP_200_OK)

            return Response(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        except ValidationError as e:
            return Response(
                {"errors": e.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def patch(self, request, *args, **kwargs):
        email = request.data.pop("email", None)
        try:
            self._maybe_update_email(request, user=request.user, new_email=email)
        except ValidationError:
            return Response(
                {"error": f"The email: `{email}` is invalid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            serializer = UserSerializer(
                request.user, data=request.data, partial=True
            )
            if serializer.is_valid():
                serializer.save()
                return Response({"data": serializer.data}, status=status.HTTP_200_OK)

            return Response(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        except ValidationError as e:
            return Response(
                {"errors": e.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UserAuthTokenView(ObtainAuthToken):
    serializer_class = AuthTokenSerializer
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                status=status.HTTP_401_UNAUTHORIZED,
                data={"error": "Not authenticated"},
            )

        token, _ = Token.objects.get_or_create(user=request.user)
        return Response({"token": token.key})

    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # delete to recreate a fresh token
        Token.objects.filter(user=user).delete()

        token, created = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})


class PasswordChangeThrottle(UserRateThrottle):
    rate = "3/h"


class UserPasswordChangeView(GenericAPIView):
    serializer_class = UserSerializer
    throttle_classes = [PasswordChangeThrottle]
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["put"]

    def put(self, request, *args, **kwargs):
        try:
            oldpassword = request.data["oldpassword"]
            password1 = request.data["password1"]
            password2 = request.data["password2"]
        except KeyError as e:
            return Response(
                {"error": f"Attribute: {e} is missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if password1 != password2:
                raise ValidationError("Password mismatch: `password1` != `password2`")  # noqa: TRY301

            if not request.user.check_password(oldpassword):
                raise ValidationError("Current password is not valid: `oldpassword`")  # noqa: TRY301

            if oldpassword == password1:
                raise ValidationError("The new and old password are identical")  # noqa: TRY301

            if not settings.DEBUG:
                validate_password(password1, user=request.user)

        except ValidationError as e:
            return Response(
                {"errors": e.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        get_adapter(request).set_password(request.user, password1)
        request.user.save()
        signals.password_changed.send(
            sender=request.user.__class__,
            request=request,
            user=request.user,
        )

        logout_on_password_change(request, request.user)

        return Response({"message:", "Password changed successfully"})
