from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import EmailField
from django_countries.fields import CountryField

from speleodb.users.managers import UserManager


def filter_permissions_by_best(permissions: list) -> list:
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
    def team_memberships(self):
        return self.rel_team_memberships.filter(is_active=True).order_by(
            "-modified_date"
        )

    @property
    def user_projects(self):
        return sorted(
            [perm.project for perm in self.permissions_user],
            key=lambda data: data.modified_date,
            reverse=True,
        )

    @property
    def team_projects(self):
        return sorted(
            [perm.project for perm in self.team_permissions],
            key=lambda data: data.modified_date,
            reverse=True,
        )

    @property
    def projects(self):
        return sorted(
            set(self.user_projects + self.team_projects),
            key=lambda data: data.modified_date,
            reverse=True,
        )

    @property
    def projects_with_level(self):
        projects = [
            {"project": perm.project, "level": perm.level}
            for perm in self.permissions_user
        ]

        return sorted(
            projects, key=lambda data: data["project"].modified_date, reverse=True
        )

    @property
    def permissions_user(self):
        return list(
            self.rel_permissions.filter(is_active=True).order_by(
                "-project__modified_date"
            )
        )

    @property
    def permissions_team(self):
        permissions = []
        for team in self.teams:
            permissions.extend(team.rel_permissions.filter(is_active=True))

        return filter_permissions_by_best(permissions)

    @property
    def permissions(self):
        return filter_permissions_by_best(self.permissions_user + self.permissions_team)
