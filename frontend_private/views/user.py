# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from typing import Any

from allauth.idp.oidc import models
from django.contrib.postgres.aggregates import ArrayAgg
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.utils import timezone
from rest_framework.authtoken.models import Token

from frontend_private.views.base import AuthenticatedTemplateView
from speleodb.campaigns.models import DonationCampaign
from speleodb.users.models import User
from speleodb.users.oidc import registered_web_origins

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpResponse

    from speleodb.utils.requests import AuthenticatedHttpRequest


# ============ Dashboard ============ #
class DashboardView(AuthenticatedTemplateView):
    template_name = "pages/dashboard.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        campaign = (
            DonationCampaign.objects.filter(
                start_date__lte=today,
                end_date__gte=today,
            )
            .order_by("-start_date", "-creation_date", "pk")
            .first()
        )
        context["donation_campaign"] = campaign
        context["campaign_should_invite"] = (
            campaign.should_invite(self.request.user) if campaign else False
        )
        return context


# ============ Setting Pages ============ #
class AccountSettingsView(AuthenticatedTemplateView):
    request: AuthenticatedHttpRequest

    def active_app_grants(self) -> QuerySet[models.Token]:
        return models.Token.objects.valid().filter(
            user=self.request.user,
            client__isnull=False,
            type__in=[models.Token.Type.ACCESS_TOKEN, models.Token.Type.REFRESH_TOKEN],
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["has_connected_apps"] = self.active_app_grants().exists()
        return context


class ProfileView(AccountSettingsView):
    template_name = "pages/user/dashboard.html"


class ConnectedAppsView(AccountSettingsView):
    template_name = "pages/user/connected_apps.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        applications = (
            self.active_app_grants()
            .values("client_id", "client__name", "client__redirect_uris")
            .annotate(granted_scopes=ArrayAgg("scopes", distinct=True))
            .order_by("client__name", "client_id")
        )
        labels = {
            "openid": "Sign in",
            "email": "Email address",
            "data:read": "Read survey data",
        }
        connected_apps = []
        for app in applications:
            origins = registered_web_origins(app["client__redirect_uris"])
            scopes = {
                scope for grant in app["granted_scopes"] for scope in grant.split()
            }
            connected_apps.append(
                {
                    "id": app["client_id"],
                    "name": app["client__name"],
                    "site": origins.pop() if len(origins) == 1 else None,
                    "permissions": [
                        labels.get(scope, scope) for scope in sorted(scopes)
                    ],
                }
            )
        context["connected_apps"] = connected_apps
        return context

    def post(
        self, request: AuthenticatedHttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        client_id = request.POST.get("revoke_client")
        if client_id:
            # Finish any in-flight exchange before deleting this user's tokens.
            User.objects.select_for_update(no_key=True).filter(
                pk=request.user.pk
            ).exists()
            models.Token.objects.filter(user=request.user, client_id=client_id).delete()
        return redirect("private:user_connected_apps")


class PassWordView(AccountSettingsView):
    template_name = "pages/user/password.html"


class AuthTokenView(AccountSettingsView):
    template_name = "pages/user/auth-token.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        context = self.get_context_data(**kwargs)
        context["auth_token"], _ = Token.objects.get_or_create(user=request.user)
        return self.render_to_response(context)

    def post(
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        with contextlib.suppress(ObjectDoesNotExist):
            Token.objects.get(user=request.user).delete()

        return self.get(request, *args, **kwargs)


class FeedbackView(AccountSettingsView):
    template_name = "pages/user/feedback.html"


class PreferencesView(AccountSettingsView):
    template_name = "pages/user/preferences.html"


class ExportsView(AccountSettingsView):
    template_name = "pages/user/exports.html"


class StationTagsView(AuthenticatedTemplateView):
    template_name = "pages/station_tags.html"
