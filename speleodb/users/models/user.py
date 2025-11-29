# -*- coding: utf-8 -*-

from __future__ import annotations

from itertools import groupby
from operator import attrgetter
from typing import TYPE_CHECKING
from typing import ClassVar

from cachetools import TTLCache
from cachetools import cached
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import EmailField
from django_countries.fields import CountryField

from speleodb.users.managers import UserManager
from speleodb.utils.exceptions import NotAuthorizedError

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django_stubs_ext import StrOrPromise

    from speleodb.gis.models import ExperimentUserPermission
    from speleodb.gis.models import Station
    from speleodb.gis.models import StationResource
    from speleodb.surveys.models import Project
    from speleodb.surveys.models import ProjectMutex
    from speleodb.surveys.models import TeamProjectPermission
    from speleodb.surveys.models import UserProjectPermission
    from speleodb.users.models import SurveyTeam
    from speleodb.users.models import SurveyTeamMembership


def filter_permissions_by_best(
    permissions: list[UserProjectPermission | TeamProjectPermission],
) -> list[UserProjectPermission | TeamProjectPermission]:
    """
    A user can have access to a project by name or from N teams.
    This function keep the "best access level" for each project
    and discard the permissions less interesting.
    Only one permission per project is being kept.
    """

    # Step 1: Sort the permissions by project and then by level in descending order
    sorted_permissions = sorted(
        permissions,
        key=lambda perm: (perm.project.id, -perm.level),
    )

    # Step 2: Group by project and keep the first (highest level) permission in each
    #         group
    grouped_permissions = []
    for _, group in groupby(sorted_permissions, key=attrgetter("project")):
        grouped_permissions.append(next(group))  # Take the first item in the group

    return sorted(grouped_permissions, key=lambda perm: perm.project.name.lower())


class User(AbstractUser):
    """
    Default custom user model for SpeleoDB.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm.
    """

    # FK Keys
    rel_experiment_permissions: models.QuerySet[ExperimentUserPermission]
    rel_mutexes: models.QuerySet[ProjectMutex]
    rel_permissions: models.QuerySet[UserProjectPermission]
    rel_stations_created: models.QuerySet[Station]
    rel_station_resources_created: models.QuerySet[StationResource]
    rel_team_memberships: models.QuerySet[SurveyTeamMembership]

    id = models.AutoField(primary_key=True)  # Explicitly declared for typing

    # First and last name do not cover name patterns around the globe
    name = CharField("Name of User", blank=False, null=False, max_length=255)
    email = EmailField("email address", unique=True)
    country = CountryField()

    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    username = None  # type: ignore[assignment]

    # ===================== User Preferences ===================== #
    email_on_speleodb_updates = BooleanField(default=True)
    email_on_projects_updates = BooleanField(default=False)
    # ------------------------------------------------------------ #

    # # ===================== User Privileges ===================== #
    is_beta_tester = BooleanField(
        default=False,
        help_text=(
            "Designates that this user has access to beta features before other users."
        ),
    )
    # # ------------------------------------------------------------ #

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    objects: ClassVar[UserManager] = UserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["name"]
        indexes = [
            # models.Index(fields=["email"]),  # Present via unique constraint
            models.Index(fields=["country"]),
        ]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name} [{self.email}]>"

    def __str__(self) -> str:
        return self.__repr__()

    @property
    def teams(self) -> models.QuerySet[SurveyTeam]:
        from speleodb.users.models import SurveyTeam  # noqa: PLC0415

        return SurveyTeam.objects.filter(
            rel_team_memberships__user=self,
            rel_team_memberships__is_active=True,
        )

    @property
    def team_memberships(self) -> models.QuerySet[SurveyTeamMembership]:
        return self.rel_team_memberships.filter(is_active=True).order_by(
            "-modified_date"
        )

    @property
    def projects(self) -> list[Project]:
        return [perm.project for perm in self.permissions]

    @property
    def projects_with_level(
        self,
    ) -> list[dict[str, Project | StrOrPromise]]:
        return [
            {"project": perm.project, "level": perm.level_label}
            for perm in self.permissions
        ]

    @property
    def permissions(self) -> list[TeamProjectPermission | UserProjectPermission]:
        """Returns a sorted list of `TeamPermission` or `UserPermission` by project
        name. The method finds the best permission (user or team) for each project."""

        user_permissions, team_permissions = self._fetch_permissions()

        return filter_permissions_by_best([*user_permissions, *team_permissions])

    @cached(cache=TTLCache(maxsize=100, ttl=300))
    def _fetch_permissions(
        self, project: Project | None = None
    ) -> tuple[QuerySet[UserProjectPermission], QuerySet[TeamProjectPermission]]:
        from speleodb.surveys.models import TeamProjectPermission  # noqa: PLC0415

        project_filter = {"project": project} if project else {}

        # -------------------------- USER PERMISSIONS -------------------------- #

        user_permissions = self.rel_permissions.filter(
            is_active=True,
            **project_filter,
        ).select_related("project")

        # -------------------------- TEAM PERMISSIONS -------------------------- #

        team_permissions = TeamProjectPermission.objects.filter(
            target__rel_team_memberships__user=self,
            target__rel_team_memberships__is_active=True,
            is_active=True,
            **project_filter,
        ).select_related("project")

        return user_permissions, team_permissions

    @cached(cache=TTLCache(maxsize=100, ttl=300))
    def get_best_permission(
        self, project: Project
    ) -> TeamProjectPermission | UserProjectPermission:
        try:
            user_permissions, team_permissions = self._fetch_permissions(project)
            return filter_permissions_by_best([*user_permissions, *team_permissions])[0]
        except IndexError as e:
            raise NotAuthorizedError(
                "The user does not have access to the project"
            ) from e

    @property
    def active_mutexes(self) -> models.QuerySet[ProjectMutex]:
        return self.rel_mutexes.filter(is_active=True)

    def has_beta_access(self) -> bool:
        return self.is_beta_tester or self.is_superuser or self.is_staff

    def void_permission_cache(self) -> None:
        self._fetch_permissions.cache_clear()
        self.get_best_permission.cache_clear()
