# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from rest_framework.authtoken.models import Token

from frontend_private.views.base import AuthenticatedTemplateView
from speleodb.background_jobs.services import can_request_export

if TYPE_CHECKING:
    from django.http import HttpResponse

    from speleodb.users.models import User
    from speleodb.utils.requests import AuthenticatedHttpRequest


# ============ Dashboard ============ #
class DashboardView(AuthenticatedTemplateView):
    template_name = "pages/dashboard.html"


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

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context: dict[str, Any] = super().get_context_data(**kwargs)
        user: User = self.request.user  # type: ignore[assignment]
        context["can_request_export"] = can_request_export(user)
        return context


class StationTagsView(AuthenticatedTemplateView):
    template_name = "pages/station_tags.html"
