# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.urls import reverse
from rest_framework.authtoken.models import Token

from frontend_private.views.base import AuthenticatedTemplateView
from speleodb.api.v2.landmark_access import collection_landmarks_queryset
from speleodb.common.enums import ColorPalette
from speleodb.common.enums import PermissionLevel
from speleodb.gis.landmark_collections import get_or_create_personal_landmark_collection
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import LandmarkCollectionUserPermission

if TYPE_CHECKING:
    from django.http import HttpResponse
    from django.http.response import HttpResponseRedirectBase

    from speleodb.users.models import User
    from speleodb.utils.requests import AuthenticatedHttpRequest


class LandmarkCollectionListingView(AuthenticatedTemplateView):
    template_name = "pages/landmark_collections.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        context = self.get_context_data(**kwargs)
        get_or_create_personal_landmark_collection(user=request.user)
        user_token, _ = Token.objects.get_or_create(user=request.user)
        context["collection_perms"] = list(
            LandmarkCollectionUserPermission.objects.filter(
                user=request.user,
                is_active=True,
                collection__is_active=True,
            )
            .select_related("collection")
            .order_by("collection__collection_type", "collection__name")
        )
        context["user_token"] = user_token
        return self.render_to_response(context)

    def post(
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        if "_refresh_user_token" in request.POST:
            Token.objects.filter(user=request.user).delete()
            Token.objects.create(user=request.user)

        return redirect(reverse("private:landmark_collections"))


class NewLandmarkCollectionView(AuthenticatedTemplateView):
    template_name = "pages/landmark_collection/new.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["default_color"] = ColorPalette.random_color()
        return context


class _BaseLandmarkCollectionView(AuthenticatedTemplateView):
    def get_collection_data(self, user: User, collection_id: str) -> dict[str, Any]:
        collection = LandmarkCollection.objects.get(
            id=collection_id,
            is_active=True,
        )
        user_perm = LandmarkCollectionUserPermission.objects.get(
            user=user,
            collection=collection,
            is_active=True,
        )

        return {
            "collection": collection,
            "has_admin_access": user_perm.level == PermissionLevel.ADMIN,
            "has_write_access": user_perm.level >= PermissionLevel.READ_AND_WRITE,
            "is_personal_collection": collection.is_personal,
            "show_permission_management": not collection.is_personal,
            "show_gis_integration": True,
            "show_danger_zone": (
                not collection.is_personal and user_perm.level == PermissionLevel.ADMIN
            ),
        }


class LandmarkCollectionDetailsView(_BaseLandmarkCollectionView):
    template_name = "pages/landmark_collection/details.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        collection_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_collection_data(
                user=request.user,
                collection_id=collection_id,
            )
        except ObjectDoesNotExist:
            return redirect(reverse("private:landmark_collections"))

        data["landmarks"] = list(
            collection_landmarks_queryset(collection=data["collection"])
        )

        return super().get(request, *args, **data, **kwargs)


class LandmarkCollectionDangerZoneView(_BaseLandmarkCollectionView):
    template_name = "pages/landmark_collection/danger_zone.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        collection_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_collection_data(
                user=request.user,
                collection_id=collection_id,
            )
        except ObjectDoesNotExist:
            return redirect(reverse("private:landmark_collections"))

        if not data["has_admin_access"]:
            return redirect(
                reverse(
                    "private:landmark_collection_details",
                    kwargs={"collection_id": collection_id},
                )
            )
        if data["is_personal_collection"]:
            return redirect(
                reverse(
                    "private:landmark_collection_details",
                    kwargs={"collection_id": collection_id},
                )
            )

        return super().get(request, *args, **data, **kwargs)


class LandmarkCollectionUserPermissionsView(_BaseLandmarkCollectionView):
    template_name = "pages/landmark_collection/user_permissions.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        collection_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_collection_data(
                user=request.user,
                collection_id=collection_id,
            )
        except ObjectDoesNotExist:
            return redirect(reverse("private:landmark_collections"))

        if data["is_personal_collection"]:
            return redirect(
                reverse(
                    "private:landmark_collection_details",
                    kwargs={"collection_id": collection_id},
                )
            )

        data["permissions"] = list(
            LandmarkCollectionUserPermission.objects.filter(
                collection=data["collection"],
                is_active=True,
            )
            .select_related("user", "collection")
            .order_by("-level", "user__email")
        )

        return super().get(request, *args, **data, **kwargs)


class LandmarkCollectionGISView(_BaseLandmarkCollectionView):
    template_name = "pages/landmark_collection/gis_integration.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        collection_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_collection_data(
                user=request.user,
                collection_id=collection_id,
            )
        except ObjectDoesNotExist:
            return redirect(reverse("private:landmark_collections"))

        return super().get(request, *args, **data, **kwargs)

    def post(
        self,
        request: AuthenticatedHttpRequest,
        collection_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_collection_data(
                user=request.user,
                collection_id=collection_id,
            )
        except ObjectDoesNotExist:
            return redirect(reverse("private:landmark_collections"))

        if "_refresh_token" in request.POST and data["has_admin_access"]:
            collection: LandmarkCollection = data["collection"]
            collection.refresh_gis_token()

        return redirect(
            reverse(
                "private:landmark_collection_gis_integration",
                kwargs={"collection_id": collection_id},
            )
        )
