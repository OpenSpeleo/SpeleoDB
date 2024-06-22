from django import template

from speleodb.surveys.models import Format
from speleodb.surveys.models import Project

register = template.Library()


@register.simple_tag
def get_survey_formats():
    return [name for _, name in Format.FileFormat.choices]


@register.simple_tag
def get_project_formats(project: Project):
    return project.rel_formats.all().order_by("_format")
