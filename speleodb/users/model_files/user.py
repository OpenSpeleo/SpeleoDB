from __future__ import annotations

from typing import TYPE_CHECKING
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import EmailField
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
    permission_map = {}
    for perm in permissions:
        if (
            perm.project not in permission_map
            or permission_map[perm.project]._level < perm._level  # noqa: SLF001
        ):
            permission_map[perm.project] = perm

    return sorted(
        permission_map.values(), key=lambda data: data.modified_date, reverse=True
    )


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
            self.rel_permissions.filter(is_active=True).order_by(
                "-project__modified_date"
            )
        )

    @property
    def permissions_team(self) -> list[TeamPermission]:
        permissions = []
        for team in self.teams:
            permissions.extend(team.rel_permissions.filter(is_active=True))

        permissions = filter_permissions_by_best(permissions)
        return sorted(permissions, key=lambda perm: perm.project.name)

    @property
    def permissions(self) -> list[TeamPermission, UserPermission]:
        permissions = filter_permissions_by_best(
            self.permissions_user + self.permissions_team
        )
        return sorted(permissions, key=lambda perm: perm.project.name)
