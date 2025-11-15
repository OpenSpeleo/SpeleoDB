# -*- coding: utf-8 -*-

from __future__ import annotations

from django import template

from speleodb.common.enums import PermissionLevel

register = template.Library()


@register.simple_tag
def get_user_project_permission_levels() -> list[PermissionLevel]:
    return PermissionLevel.members  # type: ignore[arg-type]


@register.simple_tag
def get_user_experiment_permission_levels() -> list[PermissionLevel]:
    return PermissionLevel.members_no_webviewer


@register.simple_tag
def get_team_permission_levels() -> list[PermissionLevel]:
    return PermissionLevel.members_no_admin
