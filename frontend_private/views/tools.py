# -*- coding: utf-8 -*-

from __future__ import annotations

from frontend_private.views.base import AuthenticatedTemplateView


class ToolXLSToArianeDMP(AuthenticatedTemplateView):
    template_name = "pages/tools/xls2dmp.html"
