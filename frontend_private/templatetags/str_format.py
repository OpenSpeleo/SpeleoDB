# -*- coding: utf-8 -*-

from __future__ import annotations

from django import template

register = template.Library()


@register.filter()
def normalize(value: str) -> str:
    label = value.replace("_", " ").title()
    return "Read & Write" if label == "Read And Write" else label
