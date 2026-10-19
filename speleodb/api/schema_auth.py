"""Configured allauth wire contracts omitted from its bundled specification.

These adaptations follow allauth's RESTView, client decorators and this site's
phone-feature middleware. They intentionally do not apply DRF transport rules:
allauth parses JSON itself and returns Django responses.
"""

from __future__ import annotations

import copy
from typing import Any

from allauth.account import app_settings as account_settings
from django.conf import settings


def _response(document: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in response:
        name = response["$ref"].rsplit("/", 1)[1]
        return copy.deepcopy(document["components"]["responses"][name])
    return response


def adapt_auth_transport(
    document: dict[str, Any],
    operation: dict[str, Any],
    client: str,
    path: str,
    method: str,
) -> None:
    """Project configured inputs, authentication and parsing onto one handler."""
    components = document["components"]
    schemas = components["schemas"]
    schemas["Email"].update(format="email", maxLength=320, minLength=1)
    schemas["Password"]["minLength"] = 1
    schemas["RefreshToken"]["minLength"] = 1
    for name in ("VerifyEmail", "ResetPassword"):
        schemas[name]["properties"]["key"]["minLength"] = 1
    change = components["requestBodies"]["ChangePassword"]["content"][
        "application/json"
    ]["schema"]
    change["properties"]["current_password"] = {
        "type": "string",
        "description": (
            "Required when the account has a usable password; optional otherwise."
        ),
    }
    change["properties"]["new_password"].update(
        minLength=1,
        description="The new password, subject to configured password validators.",
    )
    primary = components["requestBodies"]["MarkPrimaryEmail"]["content"][
        "application/json"
    ]["schema"]
    primary["properties"]["email"].update(format="email", minLength=1, maxLength=320)
    if {account_settings.LoginMethod.EMAIL} == account_settings.LOGIN_METHODS:
        schemas["Login"] = {
            "type": "object",
            "properties": {
                "email": {"$ref": "#/components/schemas/Email"},
                "password": {"$ref": "#/components/schemas/Password"},
            },
            "required": ["email", "password"],
        }
    disabled_phone = (
        path == "account/phone" or path.startswith("auth/phone/")
    ) and "phone" not in account_settings.SIGNUP_FIELDS
    parameters = operation.setdefault("parameters", [])
    parameters[:] = [
        parameter
        for parameter in parameters
        if parameter.get("$ref") != "#/components/parameters/SessionToken"
    ]
    schemes = components.setdefault("securitySchemes", {})
    if client == "app" and not disabled_phone:
        parameters.append({"$ref": "#/components/parameters/SessionToken"})
        schemes["SessionToken"] = {
            "type": "apiKey",
            "in": "header",
            "name": "X-Session-Token",
            "description": "App session identity; browser cookies are ignored.",
        }
        operation["security"] = [{"SessionToken": []}, {}]
    elif client == "browser":
        operation["responses"].pop("410", None)
        schemes["BrowserSession"] = {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.SESSION_COOKIE_NAME,
        }
        operation["security"] = [{"BrowserSession": []}, {}]
        if method not in {"get", "head", "options"}:
            parameters.append(
                {
                    "in": "header",
                    "name": "X-CSRFToken",
                    "required": True,
                    "description": (
                        "CSRF token corresponding to the browser's CSRF cookie. "
                        "Required even for an anonymous browser request."
                    ),
                    "schema": {"type": "string"},
                }
            )
            forbidden = _response(
                document,
                operation["responses"].get(
                    "403", {"description": "Browser CSRF verification failed."}
                ),
            )
            forbidden.setdefault("content", {})["text/html"] = {
                "schema": {"type": "string"}
            }
            operation["responses"]["403"] = forbidden
    else:
        operation["security"] = [{}]

    body = operation.get("requestBody")
    if body:
        if "$ref" in body:
            body = components["requestBodies"][body["$ref"].rsplit("/", 1)[1]]
        body["required"] = True
    disabled_input = (
        disabled_phone
        or (path == "auth/code/confirm" and not account_settings.LOGIN_BY_CODE_ENABLED)
        or path == "auth/email/verify/resend"
    )
    if method != "get" and not disabled_input:
        bad_request = _response(
            document,
            operation["responses"].get(
                "400", {"description": "Malformed JSON, UTF-8 or non-object body."}
            ),
        )
        bad_request.setdefault("content", {})["text/html"] = {
            "schema": {"type": "string", "minLength": 0, "maxLength": 0}
        }
        operation["responses"]["400"] = bad_request
    if path == "auth/email/verify" and not (
        account_settings.EMAIL_VERIFICATION_BY_CODE_ENABLED
    ):
        operation["responses"].pop("409", None)
    if not account_settings.PASSWORD_RESET_BY_CODE_ENABLED:
        if path == "auth/password/reset":
            operation["responses"].pop("409", None)
        if path == "auth/password/request":
            operation["responses"].pop("401", None)
