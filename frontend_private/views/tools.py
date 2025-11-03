# -*- coding: utf-8 -*-

from __future__ import annotations

from frontend_private.views.base import AuthenticatedTemplateView


class ToolXLSToArianeDMP(AuthenticatedTemplateView):
    template_name = "pages/tools/xls2dmp.html"


class ToolXLSToCompass(AuthenticatedTemplateView):
    template_name = "pages/tools/xls2compass.html"


class ToolDMP2Json(AuthenticatedTemplateView):
    template_name = "pages/tools/dmp2json.html"
