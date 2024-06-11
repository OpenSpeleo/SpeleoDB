from django import template

from speleodb.surveys.models import Project

register = template.Library()


@register.simple_tag
def get_visibility_scopes():
    return list(Project.Visibility._member_names_)
