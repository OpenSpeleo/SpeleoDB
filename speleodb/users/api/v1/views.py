#!/usr/bin/env python
# -*- coding: utf-8 -*-

import contextlib

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import permissions
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken as _ObtainAuthToken
from rest_framework.response import Response

from speleodb.users.api.v1.serializers import AuthTokenSerializer
from speleodb.users.api.v1.serializers import UserSerializer
from speleodb.utils.helpers import str2bool
from speleodb.utils.helpers import wrap_response_with_status
from speleodb.utils.view_cls import CustomAPIView


class UserPreference(CustomAPIView):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["patch"]

    def _patch(self, request, *args, **kwargs):
        try:
            request.user.email_on_projects_updates = str2bool(
                request.data["email_on_projects_updates"]
            )
            request.user.email_on_speleodb_updates = str2bool(
                request.data["email_on_speleodb_updates"]
            )
        except KeyError as e:
            return Response(
                {"errror": f"Attribute: {e} is missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.save()
        serializer = UserSerializer(request.user)

        return serializer.data


class ObtainAuthToken(_ObtainAuthToken):
    serializer_class = AuthTokenSerializer

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return wrap_response_with_status(
                lambda *a, **kw: Response(
                    status=status.HTTP_401_UNAUTHORIZED,
                    data={"error": "Not authenticated"},
                ),
                request,
            )
        token, created = Token.objects.get_or_create(user=request.user)
        return wrap_response_with_status(
            lambda *a, **kw: Response({"token": token.key}), request
        )

    def post(self, request, *args, **kwargs):
        return wrap_response_with_status(super().post, request, *args, **kwargs)

    def _patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # delete to recreate a fresh token
        with contextlib.suppress(ObjectDoesNotExist):
            Token.objects.get(user=user).delete()

        token, created = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})

    def patch(self, request, *args, **kwargs):
        return wrap_response_with_status(self._patch, request, *args, **kwargs)
