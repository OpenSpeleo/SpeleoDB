# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import HttpRequest
from rest_framework.request import Request

if TYPE_CHECKING:
    from speleodb.users.models import User


class AuthenticatedDRFRequest(Request):
    user: User


class AuthenticatedHttpRequest(HttpRequest):
    user: User
