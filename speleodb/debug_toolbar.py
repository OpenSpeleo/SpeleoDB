from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import resolve

from frontend_public.urls import ArianeWebView

if TYPE_CHECKING:
    from django.http import HttpRequest


def show_toolbar(request: HttpRequest) -> bool:
    # The toolbar renders correctly except for my view.
    return resolve(request.path).func not in [ArianeWebView]
