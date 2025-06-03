# -*- coding: utf-8 -*-

from __future__ import annotations

from django import template

from speleodb.surveys.models import PermissionLevel

register = template.Library()


@register.simple_tag
def get_user_permission_levels() -> list[PermissionLevel]:
    return PermissionLevel.members  # type: ignore[arg-type,return-value]


@register.simple_tag
def get_team_permission_levels() -> list[PermissionLevel]:
    return PermissionLevel.members_no_admin
