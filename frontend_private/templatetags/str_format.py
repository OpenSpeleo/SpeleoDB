from django import template

register = template.Library()


@register.filter()
def normalize(value: str) -> str:
    return value.replace("_", " ").title()
