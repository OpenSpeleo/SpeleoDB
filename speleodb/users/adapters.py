# -*- coding: utf-8 -*-

from __future__ import annotations

import typing

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core import context as _allauth_context
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site

if typing.TYPE_CHECKING:
    from typing import Any

    from django.contrib.auth.base_user import AbstractBaseUser
    from django.forms import BaseForm
    from django.http import HttpRequest

    from speleodb.users.models import User


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def save_user(
        self,
        request: HttpRequest,
        user: AbstractBaseUser,
        form: BaseForm,
        commit: bool = True,
    ) -> AbstractBaseUser:
        # allauth saves before calling SignupForm.signup(), so required profile
        # fields must be populated before its first INSERT.
        speleodb_user: User = typing.cast("User", user)
        speleodb_user.name = form.cleaned_data["name"]
        speleodb_user.country = form.cleaned_data["country"]
        return super().save_user(request, user, form, commit=commit)

    def send_mail(
        self, template_prefix: str, email: str, context: dict[str, Any]
    ) -> None:
        request = _allauth_context.request
        ctx = {
            "request": request,
            "email": email,
            "current_site": get_current_site(request),
        }
        ctx.update(context)
        msg = self.render_mail(template_prefix, email, ctx)
        msg.send(fail_silently=True)
