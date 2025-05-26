from django.http import HttpRequest
from rest_framework.request import Request

from speleodb.users.models import User


class AuthenticatedDRFRequest(Request):
    user: User


class AuthenticatedHttpRequest(HttpRequest):
    user: User
