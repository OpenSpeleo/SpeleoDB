from django import template

from speleodb.surveys.models import Permission

register = template.Library()


@register.simple_tag
def get_permission_levels():
    return [name for _, name in Permission.Level.choices]
