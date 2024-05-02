from rest_framework.exceptions import APIException


class NotAuthorizedError(APIException):
    status_code = 401
    default_detail = "You are not allowed to execute this action."
    default_code = "not_allowed"


class ResourceBusyError(APIException):
    status_code = 409
    default_detail = "The resource you are trying to acquire is currently busy."
    default_code = "not_allowed"
