# -*- coding: utf-8 -*-

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class AuthenticatedTemplateView(LoginRequiredMixin, TemplateView): ...
