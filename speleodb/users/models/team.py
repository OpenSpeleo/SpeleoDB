# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from cachetools import TTLCache
from cachetools import cached
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django_countries.fields import CountryField

from speleodb.users.models import User
from speleodb.utils.django_base_models import BaseIntegerChoices

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise

    from speleodb.surveys.models import TeamPermission


class SurveyTeam(models.Model):
    """
    Represents a survey team with multiple members.
    Each member has a role (Leader or Member) with timestamps for auditing changes.
    """

    rel_team_memberships: models.QuerySet[SurveyTeamMembership]
    rel_permissions: models.QuerySet[TeamPermission]

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=False, null=False)

    country = CountryField(null=False, blank=False)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ["name"]
        verbose_name = "Survey Team"
        verbose_name_plural = "Survey Teams"

    def __str__(self) -> str:
        return str(self.name)

    @cached(cache=TTLCache(maxsize=100, ttl=30))
    def get_membership(self, user: User) -> SurveyTeamMembership:
        return self.rel_team_memberships.get(user=user, is_active=True)

    def get_member_count(self) -> int:
        return self.get_all_memberships().count()

    def get_all_memberships(self) -> models.QuerySet[SurveyTeamMembership]:
        return (
            self.rel_team_memberships.filter(is_active=True)
            .select_related("user")
            .order_by("-role", "user__email")
        )

    def is_member(self, user: User) -> bool:
        try:
            _ = self.get_membership(user=user)
            return True
        except ObjectDoesNotExist:
            return False

    def is_leader(self, user: User) -> bool:
        try:
            return (
                self.get_membership(user=user).role == SurveyTeamMembershipRole.LEADER
            )
        except ObjectDoesNotExist:
            return False


class SurveyTeamMembershipRole(BaseIntegerChoices):
    MEMBER = (0, "MEMBER")
    LEADER = (1, "LEADER")


class SurveyTeamMembership(models.Model):
    """
    Through model to manage the many-to-many relationship between SurveyTeam and User.
    Tracks the role of the user in the team (Leader or Member) and the timestamps for
    role changes.
    """

    team = models.ForeignKey(
        SurveyTeam,
        on_delete=models.CASCADE,
        related_name="rel_team_memberships",
        blank=False,
        null=False,
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="rel_team_memberships",
        blank=False,
        null=False,
    )

    is_active = models.BooleanField(default=True)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    deactivated_by = models.ForeignKey(
        User,
        related_name="rel_deactivated_memberships",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        default=None,
    )

    role = models.IntegerField(
        choices=SurveyTeamMembershipRole.choices,
        default=SurveyTeamMembershipRole.MEMBER,
        verbose_name="role",
        null=False,
        blank=False,
    )

    class Meta:
        unique_together = ("user", "team")
        verbose_name = "Team Membership"
        verbose_name_plural = "Team Memberships"

    def __str__(self) -> str:
        return f"{self.user} => {self.team} [{self.role_label}]"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    @property
    def role_label(self) -> StrOrPromise:
        return SurveyTeamMembershipRole.from_value(self.role).label

    def deactivate(self, deactivated_by: User) -> None:
        self.is_active = False
        self.deactivated_by = deactivated_by
        self.save()

    def reactivate(self, role: SurveyTeamMembershipRole) -> None:
        self.is_active = True
        self.deactivated_by = None
        self.role = role
        self.save()
