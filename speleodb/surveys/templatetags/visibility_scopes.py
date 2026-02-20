# -*- coding: utf-8 -*-

from __future__ import annotations

from django import template

from speleodb.common.enums import ProjectVisibility

register = template.Library()


@register.simple_tag
def get_visibility_scopes() -> list[str]:
    return [str(name) for _, name in ProjectVisibility.choices]
