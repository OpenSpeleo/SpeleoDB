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
    ProjectType.ARIANE: "bg-[#99E5EA]",
    ProjectType.COMPASS: "bg-[#BCADEC]",
    ProjectType.STALAGMIGHT: "bg-[#F0C17A]",
    ProjectType.STICKMAPS: "bg-[#F99099]",
    ProjectType.THERION: "bg-[#9FE88E]",
    ProjectType.WALLS: "bg-[#C9E885]",
    ProjectType.OTHER: "bg-[#BCBCBC]",
}


@register.simple_tag
def get_project_types() -> list[str]:
    """Return list of project type display names."""
    return [str(name) for _, name in ProjectType.choices]


@register.simple_tag
def get_project_type_colors() -> dict[str, str]:
    """Expose the canonical badge classes to template-owned visualizations."""
    return PROJECT_TYPE_COLORS


@register.simple_tag
def get_project_type_color(project_type: str) -> str:
    """Return the CSS background color class for a project type."""
    return PROJECT_TYPE_COLORS.get(project_type, PROJECT_TYPE_COLORS[ProjectType.OTHER])


@register.simple_tag
def get_project_type_display(project_type: str) -> str | StrOrPromise:
    """Return the display name for a project type value."""
    # ProjectType.choices returns tuples of (value, display_name)
    type_map = dict(ProjectType.choices)
    return type_map.get(
        project_type, project_type.upper() if project_type else "UNKNOWN"
    )
