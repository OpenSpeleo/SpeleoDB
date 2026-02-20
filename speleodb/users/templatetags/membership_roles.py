# -*- coding: utf-8 -*-

from __future__ import annotations

from django import template

from speleodb.common.enums import SurveyTeamMembershipRole

register = template.Library()


@register.simple_tag
def get_membership_roles() -> list[str]:
    return [str(name) for _, name in SurveyTeamMembershipRole.choices]
