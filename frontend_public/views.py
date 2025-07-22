# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import TypeVar

from django.conf import settings
from django.shortcuts import redirect
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView

from frontend_public.models import BoardMember
from frontend_public.models import ExplorerMember
from frontend_public.models import TechnicalMember

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest
    from django.http.response import HttpResponse
    from django.http.response import HttpResponseRedirectBase

RT = TypeVar("RT")


def redirect_authenticated_user[RT](
    func: Callable[..., RT],
) -> Callable[..., RT | HttpResponseRedirectBase]:
    def wrapper(
        obj: object, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> RT | HttpResponseRedirectBase:
        if request.user.is_authenticated:
            return redirect("private:user_dashboard")

        return func(obj, request, *args, **kwargs)

    return wrapper


class LoginView(View):
    template_name = "auth/login.html"

    @redirect_authenticated_user
    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            LoginView.template_name,
        )


class PasswordResetFromKeyView(View):
    template_name = "auth/password_reset_from_key.html"

    @redirect_authenticated_user
    def get(self, request: HttpRequest, uidb36: str, key: str) -> HttpResponse:
        return render(
            request,
            PasswordResetFromKeyView.template_name,
            {
                "uidb36": uidb36,
                "key": key,
            },
        )


class PasswordResetView(View):
    template_name = "auth/password_reset.html"

    @redirect_authenticated_user
    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            PasswordResetView.template_name,
        )


class SignUpView(View):
    template_names = {
        True: "auth/signup.html",
        False: "auth/signup_closed.html",
    }

    @redirect_authenticated_user
    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            SignUpView.template_names[settings.ACCOUNT_ALLOW_REGISTRATION],
        )


class PeoplePageView(TemplateView):
    """View for displaying all people involved in the organization."""

    template_name = "pages/people.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Add people data to context."""
        context = super().get_context_data(**kwargs)

        # Fetch all people, already ordered by order then name
        context["board_members"] = BoardMember.objects.all()
        context["technical_members"] = TechnicalMember.objects.all()
        context["explorer_members"] = ExplorerMember.objects.all()

        return context
