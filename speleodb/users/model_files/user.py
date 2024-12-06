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
    def projects(self):
        return [perm.project for perm in self.get_all_permissions()]

    def get_all_permissions(self):
        return self.rel_permissions.filter(is_active=True)

    def get_all_projects(self):
        projects = [
            {"project": perm.project, "level": perm.level}
            for perm in self.get_all_permissions()
        ]
        return sorted(
            projects, key=lambda data: data["project"].modified_date, reverse=True
        )

    def get_all_team_memberships(self):  # -> list[SurveyTeamMembership]
        return self.rel_team_memberships.filter(is_active=True)

    def get_all_teams(self):  # -> list[SurveyTeam]
        teams = [
            {"team": membership.team, "role": membership.role}
            for membership in self.get_all_team_memberships()
        ]
        return sorted(teams, key=lambda data: data["team"].modified_date, reverse=True)
