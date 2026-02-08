# -*- coding: utf-8 -*-

from __future__ import annotations

import typing

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core import context as _allauth_context
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site

if typing.TYPE_CHECKING:
    from typing import Any

    from django.http import HttpRequest


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

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
        msg = self.render_mail(template_prefix, email, ctx)  # type: ignore[no-untyped-call]
        msg.send(fail_silently=True)
