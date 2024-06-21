from django import template

from speleodb.surveys.models import Format

register = template.Library()


@register.simple_tag
def get_survey_formats():
    return [name for _, name in Format.FileFormat.choices]
