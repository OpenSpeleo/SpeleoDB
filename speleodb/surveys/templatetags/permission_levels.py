from django import template

from speleodb.surveys.models import PermissionLevel

register = template.Library()


@register.simple_tag
def get_user_permission_levels() -> list[str]:
    return [name for _, name in PermissionLevel.choices]


@register.simple_tag
def get_team_permission_levels() -> list[str]:
    return [name for _, name in PermissionLevel.choices_no_admin]
