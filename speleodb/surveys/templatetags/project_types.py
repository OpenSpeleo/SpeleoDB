# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django import template

from speleodb.common.enums import ProjectType

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise

register = template.Library()

# Color mapping for each project type (survey software)
# Using distinctive Tailwind CSS background classes
PROJECT_TYPE_COLORS: dict[str, str] = {
    ProjectType.ARIANE: "bg-sky-600",
    ProjectType.COMPASS: "bg-emerald-600",
    ProjectType.STICKMAPS: "bg-violet-600",
    ProjectType.THERION: "bg-amber-600",
    ProjectType.WALLS: "bg-red-500",
    ProjectType.OTHER: "bg-slate-500",
}


@register.simple_tag
def get_project_types() -> list[str]:
    """Return list of project type display names."""
    return [str(name) for _, name in ProjectType.choices]


@register.simple_tag
def get_project_type_color(project_type: str) -> str:
    """Return the CSS background color class for a project type."""
    return PROJECT_TYPE_COLORS.get(project_type, "bg-slate-500")


@register.simple_tag
def get_project_type_display(project_type: str) -> str | StrOrPromise:
    """Return the display name for a project type value."""
    # ProjectType.choices returns tuples of (value, display_name)
    type_map = dict(ProjectType.choices)
    return type_map.get(
        project_type, project_type.upper() if project_type else "UNKNOWN"
    )
