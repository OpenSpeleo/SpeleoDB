from django import template

register = template.Library()


@register.filter(name="is_in_list")
def is_in_list(value, values: str | list) -> bool:
    if isinstance(values, str):
        values = values.split(",")
    return value in values
