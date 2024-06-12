from django import template

register = template.Library()


@register.filter(name="is_in_list")
def is_in_list(value, given_list):
    return value in given_list
