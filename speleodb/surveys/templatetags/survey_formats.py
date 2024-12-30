from django import template

from speleodb.surveys.models import Format
from speleodb.surveys.models import Project

register = template.Library()


@register.simple_tag
def get_survey_formats() -> list[str]:
    return [name for _, name in Format.FileFormat.choices]


@register.simple_tag
def get_project_formats(project: Project) -> list[Format]:
    return [
        _format
        for _format in project.rel_formats.all().order_by("_format")
        if _format.raw_format not in Format.FileFormat.__excluded_download_formats__
    ]
