from rest_framework.exceptions import APIException


class ProjectNotFound(APIException):
    status_code = 404
    default_detail = "The project was not found. No previous upload has been made."
    default_code = "not_found"


class CommitIDNotFound(APIException):
    status_code = 404
    default_detail = "The project was not found. No previous upload has been made."
    default_code = "not_found"


class NotAuthorizedError(APIException):
    status_code = 401
    default_detail = "You are not allowed to execute this action."
    default_code = "not_allowed"


class ResourceBusyError(APIException):
    status_code = 409
    default_detail = "The resource you are trying to acquire is currently busy."
    default_code = "not_allowed"


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "Service temporarily unavailable, try again later."
    default_code = "service_unavailable"
