# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.http import HttpRequest
from rest_framework.exceptions import ParseError
from rest_framework.request import Request

if TYPE_CHECKING:
    from speleodb.users.models import User


class AuthenticatedDRFRequest(Request):
    user: User


class AuthenticatedHttpRequest(HttpRequest):
    user: User


def require_mapping_request_data(
    data: dict[str, Any] | list[Any],
) -> dict[str, Any]:
    """Return object-shaped request data or reject an incompatible body."""
    if not isinstance(data, dict):
        raise ParseError("Request body must be a JSON object.")
    return data
