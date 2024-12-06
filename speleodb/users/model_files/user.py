from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import EmailField
from django_countries.fields import CountryField

from speleodb.users.managers import UserManager


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
            [perm.project for perm in self.get_all_permissions()],
            key=lambda data: data["project"].modified_date,
            reverse=True,
        )

    @property
    def team_projects(self):
        return sorted(
            [
                team_membership.project
                for team_membership in self.rel_team_memberships.filter(is_active=True)
            ],
            key=lambda data: data["project"].modified_date,
            reverse=True,
        )

    @property
    def projects(self):
        return sorted(
            set(self.user_projects + self.team_projects),
            key=lambda data: data["project"].modified_date,
            reverse=True,
        )

    @property
    def projects_with_level(self):
        projects = [
            {"project": perm.project, "level": perm.level}
            for perm in self.get_all_permissions()
        ]

        return sorted(
            projects, key=lambda data: data["project"].modified_date, reverse=True
        )

    def get_all_permissions(self):
        return self.rel_permissions.filter(is_active=True)

    # def get_team_all_permissions(self):
    #     return self.rel_permissions.filter(is_active=True)
