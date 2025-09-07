# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

from django.db import connections
from rest_framework import permissions
from rest_framework import status
from rest_framework.views import APIView

from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response

logger = logging.getLogger(__name__)


class StatusApiView(APIView):
    permission_classes = [permissions.AllowAny]
    schema = None

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return SuccessResponse()


class HealthCheckApiView(APIView):
    permission_classes = [permissions.AllowAny]
    schema = None

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # Verify DB is connected
        healthy, errors = self._perform_healthchecks()

        if healthy:
            return SuccessResponse()

        return ErrorResponse(
            {"errors": errors},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    def _perform_healthchecks(self) -> tuple[bool, list[str]]:
        errors = []

        # Run a SQL query against the specified database.
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as e:
            logger.exception("Database connection failed")
            errors.append(str(e))

        return not errors, errors
