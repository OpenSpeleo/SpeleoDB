"""Explicit schemas for mounted machine-discovery and Git smart-HTTP APIs."""

from __future__ import annotations

import copy
from typing import Any

from django.conf import settings
from drf_spectacular.renderers import OpenApiJsonRenderer
from drf_spectacular.renderers import OpenApiJsonRenderer2
from drf_spectacular.renderers import OpenApiYamlRenderer
from drf_spectacular.renderers import OpenApiYamlRenderer2
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from speleodb.api.schema_auto import drf_transport_parameters
from speleodb.api.schema_auto import project_drf_responses
from speleodb.git_proxy.views import UPSTREAM_ERROR_MESSAGE
from well_known.views import apple_app_site_association
from well_known.views import assetlinks
from well_known.views import passkey_endpoints

_BINARY = {"type": "string", "format": "binary"}
_STRING = {"type": "string"}
_CACHE_HEADERS = {
    name: {"schema": _STRING} for name in ("Cache-Control", "Expires", "Pragma")
}


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties)}


def _array(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": items}


def _discovery_operation(
    operation_id: str, schema: dict[str, Any], view: APIView
) -> dict[str, Any]:
    responses = project_drf_responses(
        {
            "200": {
                "description": "Machine discovery document.",
                "content": {"application/json": {"schema": schema}},
            }
        },
        view,
        "GET",
    )
    # Django JsonResponse always returns JSON, bypassing DRF success rendering.
    responses["200"]["content"] = {"application/json": {"schema": schema}}
    return {
        "operationId": operation_id,
        "tags": ["Discovery"],
        "parameters": drf_transport_parameters(view, "GET"),
        "security": [{"cookieAuth": []}, {"tokenAuth": []}, {"bearerAuth": []}, {}],
        "responses": responses,
    }


def _git_paths() -> dict[str, Any]:
    paths: dict[str, Any] = {}
    for service, suffix, operation_id in (
        (None, "info/refs", "git_info_refs"),
        ("git-upload-pack", "git-upload-pack", "git_upload_pack"),
        ("git-receive-pack", "git-receive-pack", "git_receive_pack"),
    ):
        discovery = service is None
        operation: dict[str, Any] = {
            "operationId": operation_id,
            "tags": ["Git smart HTTP"],
            "description": (
                "Opaque Git packet-line protocol. Protocol rejection can use HTTP 200; "
                "the Git client must interpret the packet body. Only the configured "
                "master branch may be pushed; receive-pack also requires the caller's "
                "active project mutex."
            ),
            "parameters": [
                {
                    "in": "path",
                    "name": "id",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                },
                *[
                    {"in": "header", "name": name, "schema": _STRING}
                    for name in (
                        "Git-Protocol",
                        "Cache-Control",
                        "Pragma",
                        "User-Agent",
                    )
                ],
                {
                    "in": "query",
                    "name": "format",
                    "schema": {"type": "string", "enum": ["text"]},
                },
            ],
            "security": [{"gitBasicAuth": []}, {"tokenAuth": []}, {"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "Git advertisement/result or packet-line rejection.",
                    "headers": copy.deepcopy(_CACHE_HEADERS),
                    "content": {},
                },
                "502": {
                    "description": "Upstream Git transport unavailable or invalid.",
                    "headers": {
                        "Cache-Control": {
                            "schema": {"type": "string", "enum": ["no-store"]}
                        }
                    },
                    "content": {
                        "text/plain": {
                            "schema": {
                                "type": "string",
                                "enum": [UPSTREAM_ERROR_MESSAGE],
                            }
                        }
                    },
                },
            },
        }
        media = operation["responses"]["200"]["content"]
        if discovery:
            operation["parameters"].append(
                {
                    "in": "query",
                    "name": "service",
                    "required": True,
                    "schema": {
                        "type": "string",
                        "enum": ["git-upload-pack", "git-receive-pack"],
                    },
                    "description": (
                        "Missing or invalid values return a Git packet-line "
                        "error with HTTP 200."
                    ),
                }
            )
            for candidate in ("git-upload-pack", "git-receive-pack"):
                media[f"application/x-{candidate}-advertisement"] = {"schema": _BINARY}
            # Invalid service is interpolated into the media type by the handler.
            media["*/*"] = {"schema": _BINARY}
            for code in ("401", "403", "404"):
                operation["responses"][code] = {
                    "description": (
                        "Authentication, permission, lookup or format rejection "
                        "rendered by GitErrorRenderer."
                    ),
                    "content": {"*/*": {"schema": _BINARY}},
                }
            operation["responses"]["401"]["headers"] = {
                "WWW-Authenticate": {"schema": _STRING}
            }
        else:
            media[f"application/x-{service}-result"] = {"schema": _BINARY}
            media["application/x-git-result"] = {"schema": _BINARY}
            operation["requestBody"] = {
                "description": "Raw Git protocol bytes, forwarded without DRF parsing.",
                "content": {
                    f"application/x-{service}-request": {"schema": _BINARY},
                    "application/octet-stream": {"schema": _BINARY},
                    "*/*": {"schema": _BINARY},
                },
            }
        paths[f"/git/{{id}}.git/{suffix}"] = {"get" if discovery else "post": operation}
    return paths


def protocol_schema() -> dict[str, Any]:
    """Declare machine APIs deliberately excluded from DRF DTO introspection."""
    android = _array(
        _object(
            {
                "relation": _array(_STRING),
                "target": _object(
                    {
                        "namespace": {"type": "string", "enum": ["android_app"]},
                        "package_name": _STRING,
                        "sha256_cert_fingerprints": _array(_STRING),
                    }
                ),
            }
        )
    )
    apple = _object(
        {
            "applinks": _object(
                {
                    "details": _array(
                        _object(
                            {
                                "appIDs": _array(_STRING),
                                "components": _array(
                                    _object({"/": _STRING, "comment": _STRING})
                                ),
                            }
                        )
                    )
                }
            ),
            "webcredentials": _object({"apps": _array(_STRING)}),
        }
    )
    paths = _git_paths()
    for path, operation_id, schema, callback in (
        ("assetlinks.json", "well_known_assetlinks", android, assetlinks),
        (
            "apple-app-site-association",
            "well_known_apple_app_site_association",
            apple,
            apple_app_site_association,
        ),
        (
            "passkey-endpoints",
            "well_known_passkey_endpoints",
            {"type": "object", "additionalProperties": False},
            passkey_endpoints,
        ),
    ):
        paths[f"/.well-known/{path}"] = {
            "get": _discovery_operation(
                operation_id,
                schema,
                callback.cls(),
            )
        }
    view = APIView()
    view.permission_classes = [AllowAny]
    view.renderer_classes = [
        OpenApiYamlRenderer,
        OpenApiYamlRenderer2,
        OpenApiJsonRenderer,
        OpenApiJsonRenderer2,
    ]
    content = {
        renderer.media_type: {
            "schema": {"type": "object", "additionalProperties": True}
            if "json" in renderer.media_type
            else _STRING
        }
        for renderer in view.get_renderers()
    }
    parameters = drf_transport_parameters(view, "GET")
    parameters.append({"in": "query", "name": "version", "schema": _STRING})
    if settings.USE_I18N:
        parameters.append({"in": "query", "name": "lang", "schema": _STRING})
    paths["/api/schema/"] = {
        "get": {
            "operationId": "api_schema_retrieve",
            "tags": ["Discovery"],
            "parameters": parameters,
            "security": [{"cookieAuth": []}, {"tokenAuth": []}, {"bearerAuth": []}, {}],
            "responses": project_drf_responses(
                {
                    "200": {
                        "description": "Complete mounted API specification.",
                        "headers": {"Content-Disposition": {"schema": _STRING}},
                        "content": content,
                    }
                },
                view,
                "GET",
            ),
        }
    }
    for response in paths["/api/schema/"]["get"]["responses"].values():
        for media, payload in response.get("content", {}).items():
            if media in {"application/yaml", "application/vnd.oai.openapi"}:
                payload["schema"] = {"type": "string"}
    return {
        "openapi": "3.0.3",
        "paths": paths,
        "components": {
            "securitySchemes": {
                "gitBasicAuth": {
                    "type": "http",
                    "scheme": "basic",
                    "description": (
                        "User email/password, or oauth2 username with the user's "
                        "API token as password."
                    ),
                }
            }
        },
    }
