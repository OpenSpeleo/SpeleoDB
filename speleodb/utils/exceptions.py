from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException


class BadRequestError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Improper Request."
    default_code = "bad_request"


class NotAuthorizedError(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "You are not allowed to execute this action."
    default_code = "not_allowed"


class UserNotActiveError(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "You are not allowed to execute this action."
    default_code = "not_allowed"


class ProjectNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "The project was not found. No previous upload has been made."
    default_code = "not_found"


class CommitIDNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "The commit ID was not found."
    default_code = "not_found"


class UserNotFoundError(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "The user was not found."
    default_code = "not_found"


class ValueNotFoundError(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Value not found."
    default_code = "not_found"


class ResourceBusyError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The resource you are trying to acquire is currently busy."
    default_code = "not_allowed"


class FileRejectedError(APIException):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    default_detail = "One of the file uploaded has been rejected for security reasons."
    default_code = "not_allowed"


class ServiceUnavailableError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Service temporarily unavailable, try again later."
    default_code = "service_unavailable"
