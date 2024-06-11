from django import template

from speleodb.surveys.models import Project

register = template.Library()


@register.simple_tag
def get_survey_softwares():
    return list(Project.Software._member_names_)
