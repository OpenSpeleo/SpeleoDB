from django import template

from speleodb.surveys.models import Project

register = template.Library()


@register.simple_tag
def get_survey_softwares():
    return [name for _, name in Project.Software.choices]
