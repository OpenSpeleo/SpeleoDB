# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import decimal
import pathlib
import uuid
from itertools import chain
from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django_countries.fields import CountryField

from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.surveys.models import PermissionLevel
from speleodb.users.models import SurveyTeam
from speleodb.users.models import User
from speleodb.utils.django_base_models import BaseIntegerChoices
from speleodb.utils.exceptions import ProjectNotFound

if TYPE_CHECKING:
    import datetime

    from speleodb.surveys.models import Format
    from speleodb.surveys.models import Mutex
    from speleodb.surveys.models import TeamPermission
    from speleodb.surveys.models import UserPermission


class ProjectManager(models.Manager["Project"]):
    """Custom manager that defers geojson field by default for performance."""

    def get_queryset(self) -> models.QuerySet["Project"]:
        """Return queryset with geojson field deferred by default."""
        return super().get_queryset().defer("geojson")

    def with_geojson(self) -> models.QuerySet["Project"]:
        """Return queryset with geojson field included."""
        return super().get_queryset()


class Project(models.Model):
    # type checking
    rel_formats: models.QuerySet[Format]
    rel_mutexes: models.QuerySet[Mutex]
    rel_user_permissions: models.QuerySet[UserPermission]
    rel_team_permissions: models.QuerySet[TeamPermission]

    # Custom manager that defers geojson by default
    objects = ProjectManager()

    # Automatic fields
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        blank=False,
        null=False,
        unique=True,
        primary_key=True,
    )
    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    name = models.CharField(max_length=255, blank=False, null=False)
    description = models.TextField(blank=False, null=False)

    country = CountryField(null=False, blank=False)

    # Optional Field
    fork_from = models.ForeignKey(
        "self",
        related_name="forks",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        default=None,
    )

    created_by = models.ForeignKey(
        User,
        related_name="rel_projects_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )

    # Geo Coordinates
    latitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(decimal.Decimal("-180.0")),
            MaxValueValidator(decimal.Decimal("180.0")),
        ],
    )

    longitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(decimal.Decimal("-180.0")),
            MaxValueValidator(decimal.Decimal("180.0")),
        ],
    )

    class Visibility(BaseIntegerChoices):
        PRIVATE = (0, "PRIVATE")
        PUBLIC = (1, "PUBLIC")

    visibility = models.IntegerField(
        choices=Visibility.choices,
        blank=False,
        null=False,
        default=Visibility.PRIVATE,
    )

    # GeoJSON data - only loaded when specifically requested
    geojson = models.JSONField(
        default=dict,
        blank=True,
        help_text="GeoJSON data for this project. Only loaded when explicitly requested.",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(latitude__isnull=True) & Q(longitude__isnull=True))
                    | (Q(latitude__isnull=False) & Q(longitude__isnull=False))
                ),
                name="Latitude & Longitude must both me null/not null simultaneously",
            )
        ]

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__}: {self.name} "
            f"[{'LOCKED' if self.active_mutex is not None else 'UNLOCKED'}]> "
        )

    def __str__(self) -> str:
        return self.name

    @property
    def active_mutex(self) -> Mutex | None:
        try:
            return self.rel_mutexes.filter(closing_user=None)[0]
        except IndexError:
            return None

    @property
    def mutex_owner(self) -> User | None:
        if (active_mutex := self.active_mutex) is None:
            return None

        return active_mutex.user

    @property
    def mutex_dt(self) -> datetime.datetime | None:
        if (active_mutex := self.active_mutex) is None:
            return None
        return active_mutex.modified_date

    def acquire_mutex(self, user: User) -> None:
        if not self.has_write_access(user):
            raise PermissionError(f"User: `{user.email} can not execute this action.`")

        # if the user is already the mutex_owner, just refresh the mutex_dt
        # => re-acquire mutex
        active_mutex = self.active_mutex
        if active_mutex is not None:
            if active_mutex.user != user:
                raise ValidationError(
                    "Another user already is currently editing this file: "
                    f"{active_mutex.user}"
                )
            active_mutex.modified_date = timezone.localtime()
            active_mutex.save()

        else:
            from speleodb.surveys.models import Mutex  # noqa: PLC0415

            _ = Mutex.objects.create(project=self, user=user)

    def release_mutex(self, user: User, comment: str = "") -> None:
        active_mutex = self.active_mutex
        if active_mutex is None:
            # if nobody owns the project, returns without error.
            return

        if self.mutex_owner != user and not self.is_admin(user):
            raise PermissionError(f"User: `{user.email} can not execute this action.`")

        # AutoSave in the background
        active_mutex.release_mutex(user=user, comment=comment)

    def get_best_permission(self, user: User) -> TeamPermission | UserPermission:
        permissions: list[TeamPermission | UserPermission] = []
        with contextlib.suppress(ObjectDoesNotExist):
            permissions.append(self.get_user_permission(user))

        for team in user.teams:
            with contextlib.suppress(ObjectDoesNotExist):
                permissions.append(self.get_team_permission(team))

        return max(permissions, key=lambda perm: perm.level)

    def get_user_permission(self, user: User) -> UserPermission:
        return self.rel_user_permissions.get(target=user, is_active=True)

    def get_team_permission(self, team: SurveyTeam) -> TeamPermission:
        return self.rel_team_permissions.get(target=team, is_active=True)

    @property
    def user_permissions(self) -> models.QuerySet[UserPermission]:
        return self.rel_user_permissions.filter(is_active=True).order_by(
            "-level", "target__email"
        )

    @property
    def team_permissions(self) -> models.QuerySet[TeamPermission]:
        return self.rel_team_permissions.filter(is_active=True).order_by(
            "-level", "target__name"
        )

    @property
    def permissions(self) -> chain[TeamPermission | UserPermission]:
        return chain(self.user_permissions, self.team_permissions)

    @property
    def user_permission_count(self) -> int:
        return self.rel_user_permissions.filter(is_active=True).count()

    @property
    def team_permission_count(self) -> int:
        return self.rel_team_permissions.filter(is_active=True).count()

    @property
    def collaborator_count(self) -> int:
        users = [
            perm.target for perm in self.rel_user_permissions.filter(is_active=True)
        ]

        teams = [
            perm.target for perm in self.rel_team_permissions.filter(is_active=True)
        ]
        for team in teams:
            users += [mbrship.user for mbrship in team.get_all_memberships()]

        users = list(set(users))
        return len(users)

    def _has_user_permission(self, user: User, permission: PermissionLevel) -> bool:
        if not isinstance(permission, PermissionLevel):
            raise TypeError(f"Unexpected value received for: `{permission=}`")

        try:
            return self.get_user_permission(user=user).level >= permission
        except ObjectDoesNotExist:
            return False

    def _has_team_permission(
        self, team: SurveyTeam, permission: PermissionLevel
    ) -> bool:
        if not isinstance(permission, PermissionLevel):
            raise TypeError(f"Unexpected value received for: `{permission=}`")

        try:
            return self.get_team_permission(team=team).level >= permission
        except ObjectDoesNotExist:
            return False

    def _has_permission(
        self, target: User | SurveyTeam, permission: PermissionLevel
    ) -> bool:
        if isinstance(target, User):
            return self._has_user_permission(user=target, permission=permission)
        if isinstance(target, SurveyTeam):
            return self._has_team_permission(team=target, permission=permission)
        raise TypeError(f"Unexpected value received for: `{target=}`")

    def has_write_access(self, user: User) -> bool:
        user_permission = self._has_user_permission(
            user, permission=PermissionLevel.READ_AND_WRITE
        )

        if user_permission:
            return True

        for team in user.teams:
            if self._has_team_permission(
                team, permission=PermissionLevel.READ_AND_WRITE
            ):
                return True

        return False

    def is_admin(self, user: User) -> bool:
        return self._has_user_permission(user, permission=PermissionLevel.ADMIN)

    @property
    def git_repo_dir(self) -> pathlib.Path:
        return pathlib.Path(settings.DJANGO_GIT_PROJECTS_DIR / str(self.id)).resolve()

    @property
    def git_repo(self) -> GitRepo:
        for _ in range(settings.DJANGO_GIT_RETRY_ATTEMPTS):
            if not self.git_repo_dir.exists():
                git_repo = GitlabManager.create_or_clone_project(self.id)
                if git_repo is None:
                    raise RuntimeError("Impossible to connect to the Gitlab API.")

                git_repo_path = pathlib.Path(git_repo.path).resolve()

                if self.git_repo_dir != git_repo_path:
                    raise ValueError(
                        f"Difference detected between `{git_repo_path=}` "
                        f"and `{self.git_repo_dir=}`"
                    )
                return git_repo

            try:
                return GitRepo.from_directory(self.git_repo_dir)
            except RuntimeError:
                # In case a `RuntimeError` is being triggered, the `project_dir` is
                # being cleaned up.
                continue

        raise RuntimeError(
            "Impossible to create, clone or open the git repository "
            f"`{self.git_repo_dir}`"
        )

    @property
    def commit_history(self) -> list[dict[str, Any]] | None:
        try:
            if (
                commit_history := GitlabManager.get_commit_history(project_id=self.id)
            ) is None:
                return []

            commits = [
                commit
                for commit in commit_history
                if commit["message"] != settings.DJANGO_GIT_FIRST_COMMIT_MESSAGE
            ]

            if isinstance(commits, (list, tuple)):
                return commits

            # No Commit was found
            return []

        except RuntimeError:
            #  Gitlab API Error
            return []

    def commit_and_push_project(self, message: str, author: User) -> str | None:
        return self.git_repo.commit_and_push_project(
            message=message, author_name=author.name, author_email=author.email
        )

    def checkout_commit_or_default_branch(self, hexsha: str | None = None) -> None:
        if not self.git_repo:
            raise ProjectNotFound("This project does not exist on gitlab or on drive")

        if hexsha is None:
            # Make sure the project is update to ToT (Top of Tree)
            self.git_repo.checkout_default_branch()

        else:
            self.git_repo.checkout_commit(hexsha=hexsha)

    @property
    def formats(self) -> models.QuerySet[Format]:
        return self.rel_formats.all().order_by("_format")

    @property
    def formats_downloadable(self) -> list[Format]:
        from speleodb.surveys.models import Format  # noqa: PLC0415

        return [
            _format
            for _format in self.formats
            if _format.raw_format not in Format.FileFormat.__excluded_download_formats__
        ]

    def refresh_geojson(self) -> None:
        """Refresh the GeoJSON data for this project."""
        # This method will be implemented by the refresh_project_geojson task
        # to populate the geojson field
        pass
