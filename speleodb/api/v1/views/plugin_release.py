# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from rest_framework import permissions
from rest_framework.generics import GenericAPIView

from speleodb.api.v1.serializers import PluginReleaseSerializer
from speleodb.plugins.models import PluginRelease
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response


class PluginReleasesApiView(GenericAPIView[PluginRelease], SDBAPIViewMixin):
    queryset = PluginRelease.objects.all()
    serializer_class = PluginReleaseSerializer

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(
            PluginRelease.objects.all().order_by("creation_date"),
            many=True,
        )

        return SuccessResponse(serializer.data)
