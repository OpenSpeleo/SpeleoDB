from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.http import Http404
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from speleodb.common.templatetags.vite_assets import current_development_generation

if TYPE_CHECKING:
    from django.http import HttpRequest


@never_cache
@require_GET
def vite_generation(request: HttpRequest) -> JsonResponse:
    if not settings.DEBUG:
        raise Http404
    return JsonResponse({"generation": current_development_generation()})
