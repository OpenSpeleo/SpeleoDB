# -*- coding: utf-8 -*-

from __future__ import annotations

from django import template

from speleodb.surveys.models import Project

register = template.Library()


@register.simple_tag
def get_visibility_scopes() -> list[str]:
    return [str(name) for _, name in Project.Visibility.choices]
