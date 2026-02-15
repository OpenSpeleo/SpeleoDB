# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny

if TYPE_CHECKING:
    from django.http import HttpRequest


@api_view(["GET"])
@permission_classes([AllowAny])  # Example of applying a permission policy
def assetlinks(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        [
            {
                "relation": [
                    "delegate_permission/common.handle_all_urls",
                    "delegate_permission/common.get_login_creds",
                ],
                "target": {
                    "namespace": "android_app",
                    "package_name": "org.speleodb.app",
                    "sha256_cert_fingerprints": [
                        "ED:5B:2F:D2:A5:F4:C3:FE:95:51:5C:B0:70:2E:1E:18:69:C5:76:C7:59:EE:31:CE:60:5C:2D:B0:1E:BC:D0:70"
                    ],
                },
            }
        ],
        content_type="application/json",
        safe=False,
    )


@api_view(["GET"])
@permission_classes([AllowAny])  # Example of applying a permission policy
def apple_app_site_association(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "applinks": {
                "apps": [],
                "details": [{"appID": "UDUF7J66TN.org.speleodb.app", "paths": ["*"]}],
            }
        },
        content_type="application/json",
    )
