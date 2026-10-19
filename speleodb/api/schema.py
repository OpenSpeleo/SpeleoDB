"""Compose the first-party, configured authentication, and OGC API contracts."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING
from typing import Any

from allauth.account import app_settings as account_settings
from allauth.headless import app_settings as headless_settings
from allauth.headless.spec.internal.schema import get_schema as get_auth_schema
from allauth.headless.tokens.strategies.sessions import SessionTokenStrategy
from django.test import override_settings
from django.urls import resolve
from drf_spectacular.generators import SchemaGenerator

from speleodb.api.schema_auth import adapt_auth_transport
from speleodb.api.schema_auto import drf_transport_parameters
from speleodb.api.schema_auto import project_drf_responses
from speleodb.api.schema_protocol import protocol_schema
from speleodb.gis.ogc_openapi import OGC_OPENAPI_DOC

if TYPE_CHECKING:
    from rest_framework.request import Request

HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})

# allauth 65.19.7 declares TooManyRequests but does not attach it to these
# account handlers. Keep the actual limiter/action mapping explicit: disabled
# features and handlers without a limiter must not advertise a 429 response.
# The limiter bypasses GET by default, including decorated account handlers.
AUTH_RATE_LIMIT_ACTIONS = {
    ("auth/login", "post"): "login",
    ("auth/signup", "post"): "signup",
    ("auth/password/request", "post"): "reset_password",
    ("auth/password/reset", "post"): "reset_password_from_key",
    ("auth/reauthenticate", "post"): "reauthenticate",
    ("account/password/change", "post"): "change_password",
    ("account/email", "post"): "manage_email",
    ("account/email", "put"): "manage_email",
    ("account/email", "patch"): "manage_email",
    ("account/email", "delete"): "manage_email",
    ("account/phone", "post"): "change_phone",
    ("auth/phone/verify/resend", "post"): "verify_phone",
}


def normalize_nullable_references(value: Any) -> None:
    """Express nullable references as an explicit OAS 3.0 null alternative.

    A nullable sibling on allOf does not make the referenced schema nullable.
    Keeping the null branch separate makes both OAS validation and generated
    TypeScript agree, without weakening the non-null object's required fields.
    """
    if isinstance(value, dict):
        if value.get("enum") == [None]:
            value.update(type="string", nullable=True)
        elif value.get("nullable") and "enum" in value and None not in value["enum"]:
            value["enum"].append(None)
        elif value.get("nullable") and any(
            key in value for key in ("$ref", "allOf", "oneOf", "anyOf")
        ):
            value.pop("nullable")
            original = dict(value)
            value.clear()
            value["anyOf"] = [
                original,
                {"type": "string", "nullable": True, "enum": [None]},
            ]
        for child in value.values():
            normalize_nullable_references(child)
    elif isinstance(value, list):
        for child in value:
            normalize_nullable_references(child)


def namespace_components(document: dict[str, Any], prefix: str) -> dict[str, Any]:
    """Give a source document's components stable, collision-free identities."""
    result = copy.deepcopy(document)
    visited: set[int] = set()

    def rewrite(value: Any) -> None:
        if isinstance(value, (dict, list)):
            if id(value) in visited:
                return
            visited.add(id(value))
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str) and reference.startswith("#/components/"):
                parts = reference.split("/", 3)
                value["$ref"] = "/".join([*parts[:3], prefix + parts[3]])
            if "security" in value:
                value["security"] = [
                    {prefix + name: scopes for name, scopes in requirement.items()}
                    for requirement in value["security"]
                ]
            for child in value.values():
                rewrite(child)
        elif isinstance(value, list):
            for child in value:
                rewrite(child)

    rewrite(result)
    for category, components in result.get("components", {}).items():
        result["components"][category] = {
            prefix + name: component for name, component in components.items()
        }
    return result


def configured_auth_schema() -> dict[str, Any]:
    """Use the installed allauth release and this application's actual settings."""
    with override_settings(ROOT_URLCONF="speleodb.api.schema_auth_urls"):
        schema: dict[str, Any] = get_auth_schema()
    paths: dict[str, Any] = {}
    for template, item in schema["paths"].items():
        clients = headless_settings.CLIENTS if "{client}" in template else ("app",)
        for client in clients:
            path = template.replace("{client}", client)
            path_item = copy.deepcopy(item)
            for method, operation in path_item.items():
                if method not in HTTP_METHODS:
                    continue
                operation["parameters"] = [
                    parameter
                    for parameter in operation.get("parameters", [])
                    if parameter.get("$ref") != "#/components/parameters/Client"
                ]
                relative_path = path.removeprefix(f"/_allauth/{client}/v1/")
                operation["operationId"] = (
                    f"auth_{client}_{relative_path.replace('/', '_')}_{method}"
                )
                operation["tags"] = [f"Authentication ({client})"]
                if (
                    relative_path == "account/phone"
                    or relative_path.startswith("auth/phone/")
                ) and "phone" not in account_settings.SIGNUP_FIELDS:
                    operation.pop("requestBody", None)
                    operation["responses"] = {
                        "409": {
                            "description": "Phone management is not configured.",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "integer", "enum": [409]}
                                        },
                                        "required": ["status"],
                                    }
                                }
                            },
                        }
                    }
                    adapt_auth_transport(
                        schema, operation, client, relative_path, method
                    )
                    continue
                if (
                    relative_path == "auth/code/confirm"
                    and not account_settings.LOGIN_BY_CODE_ENABLED
                ) or (
                    relative_path == "auth/email/verify/resend"
                    and not account_settings.EMAIL_VERIFICATION_BY_CODE_ENABLED
                ):
                    operation["responses"] = {"409": operation["responses"]["409"]}
                    operation.pop("requestBody", None)
                if (
                    relative_path == "tokens/refresh"
                    and type(headless_settings.TOKEN_STRATEGY) is SessionTokenStrategy
                ):
                    operation["responses"] = {"400": operation["responses"]["400"]}
                rate_action = AUTH_RATE_LIMIT_ACTIONS.get((relative_path, method))
                if (
                    relative_path == "auth/email/verify/resend"
                    and method == "post"
                    and account_settings.EMAIL_VERIFICATION_BY_CODE_ENABLED
                ):
                    rate_action = "confirm_email"
                if rate_action and account_settings.RATE_LIMITS.get(rate_action):
                    operation["responses"]["429"] = {
                        "$ref": "#/components/responses/TooManyRequests"
                    }
                if client == "app":
                    # The token context runs before every handler, including
                    # public configuration and disabled-feature endpoints.
                    operation["responses"].setdefault(
                        "410", {"$ref": "#/components/responses/SessionGone"}
                    )
                # allauth's authentication guard precedes these handlers but
                # 65.19.7's bundled document omits their anonymous 401 branch.
                if relative_path == "auth/reauthenticate" or (
                    relative_path == "account/email"
                    and method in {"put", "patch", "delete"}
                ):
                    operation["responses"].setdefault(
                        "401", {"$ref": "#/components/responses/Authentication"}
                    )
                adapt_auth_transport(schema, operation, client, relative_path, method)
            paths[path] = path_item
    for path, item in list(paths.items()):
        alias = copy.deepcopy(item)
        for method, operation in alias.items():
            if method in HTTP_METHODS:
                operation["operationId"] = operation["operationId"].replace(
                    "auth_", "auth_alias_", 1
                )
        paths[path.replace("/_allauth/", "/api/auth/", 1)] = alias
    schema["paths"] = paths
    # App responses can expose a newly established session token even when
    # throttled. APIResponse adds this metadata; browser responses omit it.
    rate_limit_schema = schema["components"]["responses"]["TooManyRequests"]["content"][
        "application/json"
    ]["schema"]
    rate_limit_schema["properties"]["meta"] = {
        "$ref": "#/components/schemas/BaseAuthenticationMeta"
    }
    rate_limit_schema["additionalProperties"] = False
    schema["components"]["schemas"]["ErrorResponse"]["required"] = ["status"]
    expired = schema["components"]["schemas"]["SessionGoneResponse"]
    expired["properties"]["data"] = {
        "type": "object",
        "properties": {
            "flows": {"type": "array", "items": {"$ref": "#/components/schemas/Flow"}}
        },
        "required": ["flows"],
    }
    expired["properties"]["meta"] = {
        "type": "object",
        "properties": {
            "is_authenticated": {"type": "string", "nullable": True, "enum": [None]}
        },
        "required": ["is_authenticated"],
    }
    # The bundled oneOf overlaps: password reauthentication also satisfies the
    # ordinary password branch unless the reauthentication marker is excluded.
    for variant in schema["components"]["schemas"]["AuthenticationMethod"]["oneOf"]:
        properties = variant.get("properties", {})
        if properties.get("method", {}).get("enum") == ["password"] and (
            "reauthenticated" not in properties
        ):
            variant["not"] = {"required": ["reauthenticated"]}
    timestamp = schema["components"]["schemas"].get("OptionalTimestamp", {})
    if "$ref" in timestamp and timestamp.get("nullable"):
        timestamp["allOf"] = [{"$ref": timestamp.pop("$ref")}]
    return namespace_components(schema, "Auth")


def ogc_schema() -> dict[str, Any]:
    """Keep the OGC service description authoritative for the shared SDK."""
    schema = namespace_components(OGC_OPENAPI_DOC, "OGC")
    base = OGC_OPENAPI_DOC["servers"][0]["url"]
    schema["paths"] = {base + path: item for path, item in schema["paths"].items()}
    # Django accepts bare SHA collections on six otherwise identical path
    # templates. OpenAPI cannot repeat a template for a different converter;
    # preserve that supported migration response on the canonical operation.
    gone = {
        "description": (
            "Deprecated bare-SHA collection. Re-add the geometry-specific layer "
            "advertised in Link."
        ),
        "headers": {
            "Link": {"schema": {"type": "string"}},
            "Cache-Control": {"schema": {"type": "string"}},
        },
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "status": {"type": "integer", "enum": [410]},
                        "detail": {"type": "string"},
                        "type": {"type": "string", "format": "uri"},
                    },
                    "required": ["title", "status", "detail", "type"],
                }
            }
        },
    }
    for path, item in schema["paths"].items():
        if (
            "/collections/{collection_id}" in path
            and any(f"/{family}/" in path for family in ("view", "user"))
            and "/landmark" not in path
        ):
            item["get"]["responses"]["410"] = copy.deepcopy(gone)
            item["get"]["x-deprecated-route-variant"] = (
                "Bare SHA collection_id (6 to 40 hexadecimal characters); "
                "canonical IDs append _points or _lines."
            )
    # The six deprecated resolver routes share these templates and return 410.
    # Their bare SHA inputs are still part of the current migration contract.
    schema["components"]["parameters"]["OGCCollectionIdParamGeometryTyped"]["schema"][
        "pattern"
    ] = "^[0-9a-fA-F]{6,40}(?:_(?:points|lines))?$"
    schema["paths"][base + "/openapi/"] = {
        "get": {
            "operationId": "ogc_service_description",
            "tags": ["OGC"],
            "parameters": [
                {"in": "header", "name": "If-None-Match", "schema": {"type": "string"}}
            ],
            "responses": {
                "200": {
                    "description": "Focused OGC OpenAPI 3.0.3 service document",
                    "headers": {
                        "ETag": {"schema": {"type": "string"}},
                        "Cache-Control": {"schema": {"type": "string"}},
                        "Content-Disposition": {
                            "schema": {"type": "string", "enum": ["inline"]}
                        },
                    },
                    "content": {
                        "application/vnd.oai.openapi+json": {
                            "schema": {"type": "object", "additionalProperties": True}
                        }
                    },
                },
                "304": {
                    "description": "Document unchanged",
                    "headers": {
                        "ETag": {"schema": {"type": "string"}},
                        "Cache-Control": {"schema": {"type": "string"}},
                    },
                },
            },
        }
    }
    for path, item in schema["paths"].items():
        sample_path = path.replace("{gis_token}", "a" * 40).replace("{key}", "a" * 40)
        collection = (
            "landmarks"
            if "/landmark-collection/" in path
            else "00000000-0000-0000-0000-000000000001"
            if "/landmark-collections/" in path
            else "a" * 40 + "_points"
        )
        sample_path = sample_path.replace("{collection_id}", collection).replace(
            "{feature_id}", "00000000-0000-0000-0000-000000000001"
        )
        # DRF adds these attributes to the callable returned by as_view().
        callback: Any = resolve(sample_path).func
        view = callback.cls(**callback.initkwargs)
        operation = item["get"]
        responses = {}
        for code, response in operation["responses"].items():
            resolved_response = (
                schema["components"]["responses"][response["$ref"].rsplit("/", 1)[1]]
                if "$ref" in response
                else response
            )
            responses[code] = copy.deepcopy(resolved_response)
        operation["responses"] = project_drf_responses(responses, view, "GET")
        parameters = {
            (
                parameter.get("in"),
                parameter.get("name"),
                parameter.get("$ref"),
            ): parameter
            for parameter in operation.get("parameters", [])
        }
        for parameter in drf_transport_parameters(view, "GET"):
            parameters[(parameter["in"], parameter["name"], None)] = parameter
        operation["parameters"] = list(parameters.values())
        operation["security"] = [
            {"cookieAuth": []},
            {"tokenAuth": []},
            {"bearerAuth": []},
            {},
        ]
    return schema


def merge_document(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Merge independent sources, rejecting silent overwrites and dialect drift."""
    if source["openapi"] != target["openapi"]:
        raise ValueError("API schema sources must use the same OpenAPI version")
    for path, item in source["paths"].items():
        if path in target["paths"]:
            raise ValueError(f"Duplicate API schema path: {path}")
        target["paths"][path] = item
    for category, components in source.get("components", {}).items():
        destination = target.setdefault("components", {}).setdefault(category, {})
        for name, component in components.items():
            if name in destination:
                raise ValueError(f"Duplicate API schema component: {category}/{name}")
            destination[name] = component


class SpeleoDBSchemaGenerator(SchemaGenerator):
    """One reproducible document for all current SpeleoDB HTTP API clients."""

    def get_schema(
        self, request: Request | None = None, public: bool = False
    ) -> dict[str, Any]:
        schema: dict[str, Any] = super().get_schema(  # type: ignore[no-untyped-call]
            request=request, public=public
        )
        # Every path includes its mount. SDK callers supply an origin; exporting
        # local versus production settings must not change generated URLs.
        schema["servers"] = [{"url": "/", "description": "SpeleoDB server origin"}]
        merge_document(schema, configured_auth_schema())
        merge_document(schema, ogc_schema())
        merge_document(schema, protocol_schema())
        normalize_nullable_references(schema)
        return schema
