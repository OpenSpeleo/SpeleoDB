#!/usr/bin/env python
# -*- coding: utf-8 -*-

from rest_framework import permissions
from rest_framework import status
from rest_framework.response import Response

from speleodb.api.v1.serializers import UserSerializer
from speleodb.utils.helpers import str2bool
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
