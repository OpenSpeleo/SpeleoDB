from __future__ import annotations

from itertools import groupby
from operator import attrgetter
from typing import TYPE_CHECKING
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import EmailField
from django.db.models.functions import Lower
from django_countries.fields import CountryField

from speleodb.users.managers import UserManager

if TYPE_CHECKING:
    from speleodb.surveys.models import Project
    from speleodb.surveys.models import TeamPermission
    from speleodb.surveys.models import UserPermission
    from speleodb.users.models import SurveyTeamMembership


def filter_permissions_by_best(
    permissions: list[UserPermission, TeamPermission],
) -> list[UserPermission, TeamPermission]:
    """
    A user can have access to a project by name or from N teams.
    This function keep the "best access level" for each project
    and discard the permissions less interesting.
    Only one permission per project is being kept.
    """

    # Step 1: Sort the permissions by project and then by _level in descending order
    sorted_permissions = sorted(
        permissions,
        key=lambda perm: (perm.project.id, -perm._level),  # noqa: SLF001
    )

    # Step 2: Group by project and keep the first (highest _level) permission in each
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

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    objects: ClassVar[UserManager] = UserManager()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name} [{self.email}]>"

    def __str__(self) -> str:
        return self.__repr__()

    @property
    def teams(self):
        return [
            team_membership.team
            for team_membership in self.rel_team_memberships.filter(
                is_active=True
            ).order_by("-modified_date")
        ]

    @property
    def team_memberships(self) -> list[SurveyTeamMembership]:
        return self.rel_team_memberships.filter(is_active=True).order_by(
            "-modified_date"
        )

    @property
    def user_projects(self) -> list[Project]:
        return sorted(
            [perm.project for perm in self.permissions_user],
            key=lambda data: data.modified_date,
            reverse=True,
        )

    @property
    def team_projects(self) -> list[Project]:
        return sorted(
            [perm.project for perm in self.team_permissions],
            key=lambda data: data.modified_date,
            reverse=True,
        )

    @property
    def projects(self) -> list[Project]:
        return sorted(
            set(self.user_projects + self.team_projects),
            key=lambda data: data.modified_date,
            reverse=True,
        )

    @property
    def projects_with_level(
        self,
    ) -> list[dict[str, Project | TeamPermission | UserPermission]]:
        projects = [
            {"project": perm.project, "level": perm.level}
            for perm in self.permissions_user
        ]

        return sorted(
            projects, key=lambda data: data["project"].modified_date, reverse=True
        )

    @property
    def permissions_user(self) -> list[UserPermission]:
        return list(
            self.rel_permissions.filter(is_active=True).order_by(Lower("project__name"))
        )

    @property
    def permissions_team(self) -> list[TeamPermission]:
        from speleodb.surveys.models import TeamPermission
        from speleodb.users.models import SurveyTeam

        active_user_teams = SurveyTeam.objects.filter(
            rel_team_memberships__user=self, rel_team_memberships__is_active=True
        )

        team_permissions = TeamPermission.objects.filter(
            target__in=active_user_teams
        ).order_by(Lower("project__name"))

        return filter_permissions_by_best(team_permissions)

    @property
    def permissions(self) -> list[TeamPermission, UserPermission]:
        return filter_permissions_by_best(self.permissions_user + self.permissions_team)
