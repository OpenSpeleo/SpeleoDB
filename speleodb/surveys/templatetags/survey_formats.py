from __future__ import annotations

from django import template

from speleodb.surveys.models import Format
from speleodb.surveys.models import Project

register = template.Library()


@register.simple_tag
def get_survey_formats() -> list[str]:
    return [str(name) for _, name in Format.FileFormat.choices]


@register.simple_tag
def get_project_formats(project: Project) -> list[Format]:
    return project.formats_downloadable
