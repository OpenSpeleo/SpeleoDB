from django import template

from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission

register = template.Library()


@register.simple_tag
def get_user_permission_levels() -> list[str]:
    return [name for _, name in UserPermission.Level.choices]


@register.simple_tag
def get_team_permission_levels() -> list[str]:
    return [name for _, name in TeamPermission.Level.choices]
