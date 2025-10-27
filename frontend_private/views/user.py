# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from rest_framework.authtoken.models import Token

from frontend_private.views.base import AuthenticatedTemplateView

if TYPE_CHECKING:
    from django.http import HttpResponse

    from speleodb.utils.requests import AuthenticatedHttpRequest


# ============ Setting Pages ============ #
class DashboardView(AuthenticatedTemplateView):
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
