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
from speleodb.utils.helpers import str2bool


class UserInfo(GenericAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "put"]

    def get(self, request, *args, **kwargs):
        return Response(UserSerializer(request.user).data)

    def put(self, request, *args, **kwargs):  # noqa: C901
        modified_attrs = {}

        for key in [
            "country",
            "email",
            "name",
            "email_on_projects_updates",
            "email_on_speleodb_updates",
        ]:
            try:
                new_value = request.data[key]

                if key == "country":
                    if new_value not in countries:
                        return Response(
                            {"error": f"The country: `{new_value}` does not exist."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    new_value = Country(code=new_value)

                elif key == "email":
                    try:
                        validate_email(new_value)
                    except ValidationError:
                        return Response(
                            {"error": f"The email: `{new_value}` is invalid."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                elif key.startswith("email_on"):
                    new_value = str2bool(new_value)

            except KeyError:
                continue

            if new_value == getattr(request.user, key):
                continue

            modified_attrs[key] = new_value

        if modified_attrs:
            with contextlib.suppress(KeyError):
                email = modified_attrs.pop("email")
                EmailAddress.objects.add_new_email(request, request.user, email)

            for key, value in modified_attrs.items():
                setattr(request.user, key, value)
            request.user.save(update_fields=modified_attrs.keys())

        serializer = UserSerializer(request.user)

        return Response(serializer.data)


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
