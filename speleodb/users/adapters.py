from __future__ import annotations

import typing

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings

if typing.TYPE_CHECKING:
    from django.http import HttpRequest


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)
