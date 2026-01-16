# -*- coding: utf-8 -*-

from __future__ import annotations

from itertools import groupby
from operator import attrgetter
from typing import TYPE_CHECKING
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import EmailField
from django_countries.fields import CountryField

from speleodb.common.caching import UserProjectPermissionCache
from speleodb.common.caching import UserProjectPermissionInfo
from speleodb.users.managers import UserManager
from speleodb.utils.exceptions import NotAuthorizedError

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django_stubs_ext import StrOrPromise

    from speleodb.gis.models import ExperimentUserPermission
    from speleodb.gis.models import Station
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
    _team_memberships: models.QuerySet[SurveyTeamMembership]
    mutexes: models.QuerySet[ProjectMutex]
    experiment_permissions: models.QuerySet[ExperimentUserPermission]
    project_user_permissions: models.QuerySet[UserProjectPermission]
    stations_created: models.QuerySet[Station]

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
            memberships__user=self,
            memberships__is_active=True,
        )

    @property
    def team_memberships(self) -> models.QuerySet[SurveyTeamMembership]:
        return self._team_memberships.filter(is_active=True).order_by("-modified_date")

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

        user_permissions, team_permissions = self.fetch_all_project_permissions()

        return filter_permissions_by_best([*user_permissions, *team_permissions])

    def fetch_all_project_permissions(
        self,
    ) -> tuple[QuerySet[UserProjectPermission], QuerySet[TeamProjectPermission]]:
        from speleodb.surveys.models import TeamProjectPermission  # noqa: PLC0415

        # -------------------------- USER PERMISSIONS -------------------------- #

        user_permissions = self.project_user_permissions.filter(
            is_active=True,
        ).select_related("project")

        # -------------------------- TEAM PERMISSIONS -------------------------- #

        team_permissions = TeamProjectPermission.objects.filter(
            target__memberships__user=self,
            target__memberships__is_active=True,
            is_active=True,
        ).select_related("project")

        return user_permissions, team_permissions

    def _fetch_project_permission_ids(
        self, project: Project
    ) -> UserProjectPermissionInfo:
        from speleodb.surveys.models import TeamProjectPermission  # noqa: PLC0415

        if (ids := UserProjectPermissionCache.get(self.pk, project.pk)) is not None:
            return ids

        user_perm_id = (
            self.project_user_permissions.filter(
                project=project,
                is_active=True,
            )
            .values_list("id", flat=True)
            .first()
        )

        team_perm_ids = TeamProjectPermission.objects.filter(
            target__memberships__user=self,
            target__memberships__is_active=True,
            project=project,
            is_active=True,
        ).values_list("id", flat=True)

        rslt = UserProjectPermissionInfo(
            user=user_perm_id,
            teams=list(team_perm_ids),
        )

        UserProjectPermissionCache.set(self.pk, project.pk, payload=rslt)
        return rslt

    def get_best_permission(
        self, project: Project
    ) -> UserProjectPermission | TeamProjectPermission:
        from speleodb.surveys.models import TeamProjectPermission  # noqa: PLC0415
        from speleodb.surveys.models import UserProjectPermission  # noqa: PLC0415

        perm_nfo = self._fetch_project_permission_ids(project)

        permissions: list[UserProjectPermission | TeamProjectPermission] = []

        if user_id := perm_nfo.user:
            permissions.extend(
                UserProjectPermission.objects.filter(id=user_id).select_related(
                    "target", "project"
                )
            )

        if team_ids := perm_nfo.teams:
            permissions.extend(
                TeamProjectPermission.objects.filter(id__in=team_ids).select_related(
                    "target", "project"
                )
            )

        if not permissions:
            raise NotAuthorizedError("The user does not have access to the project")

        return filter_permissions_by_best(permissions)[0]

    @property
    def active_mutexes(self) -> models.QuerySet[ProjectMutex]:
        return self.mutexes.filter(is_active=True)

    def has_beta_access(self) -> bool:
        return self.is_beta_tester or self.is_superuser or self.is_staff
