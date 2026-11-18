# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework.authtoken.models import Token

from frontend_private.views.base import AuthenticatedTemplateView
from speleodb.campaigns.models import DonationCampaign

if TYPE_CHECKING:
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
class ProfileView(AuthenticatedTemplateView):
    template_name = "pages/user/dashboard.html"


class PassWordView(AuthenticatedTemplateView):
    template_name = "pages/user/password.html"


class AuthTokenView(AuthenticatedTemplateView):
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


class FeedbackView(AuthenticatedTemplateView):
    template_name = "pages/user/feedback.html"


class PreferencesView(AuthenticatedTemplateView):
    template_name = "pages/user/preferences.html"


class ExportsView(AuthenticatedTemplateView):
    template_name = "pages/user/exports.html"


class StationTagsView(AuthenticatedTemplateView):
    template_name = "pages/station_tags.html"
