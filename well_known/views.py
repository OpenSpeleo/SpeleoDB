# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.http import HttpResponsePermanentRedirect


@api_view(["GET"])
@permission_classes([AllowAny])
def assetlinks(request: HttpRequest) -> JsonResponse:
    """This view allow SpeleoDB Android app to use password managers with
    `www.speleodb.org` domain"""
    return JsonResponse(
        [
            {
                "relation": [
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
@permission_classes([AllowAny])
def apple_app_site_association(request: HttpRequest) -> JsonResponse:
    """This view allow SpeleoDB iOS app to use password managers with
    `www.speleodb.org` domain"""

    return JsonResponse(
        {"webcredentials": {"apps": ["UDUF7J66TN.org.speleodb.app"]}},
        content_type="application/json",
    )


@permission_classes([AllowAny])
def change_password(request: HttpRequest) -> HttpResponsePermanentRedirect:
    """Helps browser/password managers send users directly to change-password when
    needed (compromised/reused password flows)."""
    return redirect(reverse("private:user_password"), permanent=True)
