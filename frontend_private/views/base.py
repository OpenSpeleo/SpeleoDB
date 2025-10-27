# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from speleodb.surveys.models import PermissionLevel
from speleodb.users.models import SurveyTeam
from speleodb.users.models import User

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise


@dataclass
class UserAccessLevel:
    ALLOWED_ACCESS_LEVELS = PermissionLevel.labels
    user: User
    level: PermissionLevel
    team: SurveyTeam | None = None

    def __init__(
        self, user: User, level: PermissionLevel | int, team: SurveyTeam | None = None
    ) -> None:
        if not isinstance(user, User):
            raise TypeError(f"`user` must be of type User: `{type(self.user)}`")
        self.user = user

        self.level = (
            PermissionLevel.from_value(level) if isinstance(level, int) else level
        )
        if not isinstance(self.level, PermissionLevel):
            raise TypeError(type(self.level))

        self.team = team
        if self.team is not None and not isinstance(self.team, SurveyTeam):
            raise TypeError(
                f"`team` must be of type SurveyTeam | None: `{type(self.team)}`"
            )

    @property
    def level_label(self) -> StrOrPromise:
        """
        Returns the label of the permission level.
        """
        return self.level.label


class AuthenticatedTemplateView(LoginRequiredMixin, TemplateView): ...
