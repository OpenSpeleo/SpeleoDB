#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import decimal
import pathlib
import uuid
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django_countries.fields import CountryField

from speleodb.git_engine.core import GitCommit
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.users.models import SurveyTeam
from speleodb.users.models import User
from speleodb.utils.exceptions import ProjectNotFound

if TYPE_CHECKING:
    import datetime

    from speleodb.surveys.models import Format
    from speleodb.surveys.models import Mutex
    from speleodb.surveys.models import TeamPermission
    from speleodb.surveys.models import UserPermission


class Project(models.Model):
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

    class Visibility(models.IntegerChoices):
        PRIVATE = (0, "PRIVATE")
        PUBLIC = (1, "PUBLIC")

    _visibility = models.IntegerField(
        choices=Visibility.choices,
        blank=False,
        null=False,
        default=Visibility.PRIVATE,
        verbose_name="visibility",
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
    def visibility(self) -> str:
        return self.Visibility(self._visibility).label

    @visibility.setter
    def visibility(self, value) -> None:
        self._visibility = value

    @property
    def active_mutex(self) -> Mutex | None:
        try:
            return self.rel_mutexes.filter(closing_user=None)[0]
        except IndexError:
            return None

    @property
    def mutex_owner(self) -> User | None:
        active_mutex: Mutex = self.active_mutex
        if active_mutex is None:
            return None

        return active_mutex.user

    @property
    def mutex_dt(self) -> datetime.datetime | None:
        active_mutex: Mutex = self.active_mutex
        if active_mutex is None:
            return None
        return active_mutex.modified_date

    def acquire_mutex(self, user: User) -> None:
        if not self.has_write_access(user):
            raise PermissionError(f"User: `{user.email} can not execute this action.`")

        # if the user is already the mutex_owner, just refresh the mutex_dt
        # => re-acquire mutex
        active_mutex: Mutex = self.active_mutex
        if active_mutex is not None:
            if active_mutex.user != user:
                raise ValidationError(
                    "Another user already is currently editing this file: "
                    f"{active_mutex.user}"
                )
            active_mutex.modified_date = timezone.localtime()
            active_mutex.save()
        else:
            from speleodb.surveys.models import Mutex

            _ = Mutex.objects.create(project=self, user=user)

    def release_mutex(self, user: User, comment: str = "") -> None:
        active_mutex: Mutex = self.active_mutex
        if active_mutex is None:
            # if nobody owns the project, returns without error.
            return

        if self.mutex_owner != user and not self.is_admin(user):
            raise PermissionError(f"User: `{user.email} can not execute this action.`")

        # AutoSave in the background
        active_mutex.release_mutex(user=user, comment=comment)

    def get_best_permission(self, user: User) -> TeamPermission | UserPermission:
        permissions = []
        with contextlib.suppress(ObjectDoesNotExist):
            permissions.append(self.get_user_permission(user))

        for team in user.teams:
            with contextlib.suppress(ObjectDoesNotExist):
                permissions.append(self.get_team_permission(team))

        return sorted(permissions, key=lambda perm: perm._level, reverse=True)[0]  # noqa: SLF001

    def get_user_permission(self, user: User) -> UserPermission:
        return self.rel_user_permissions.get(target=user, is_active=True)

    def get_team_permission(self, team: SurveyTeam) -> TeamPermission:
        return self.rel_team_permissions.get(target=team, is_active=True)

    @property
    def user_permissions(self) -> list[UserPermission]:
        return self.rel_user_permissions.filter(is_active=True).order_by(
            "-_level", "target__email"
        )

    @property
    def team_permissions(self) -> list[TeamPermission]:
        return self.rel_team_permissions.filter(is_active=True).order_by(
            "-_level", "target__name"
        )

    @property
    def permissions(self) -> list[TeamPermission, UserPermission]:
        return self.user_permissions + self.team_permissions

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

    def _has_user_permission(self, user: User, permission) -> bool:
        from speleodb.surveys.models.permission_user import UserPermission

        if not isinstance(permission, UserPermission.Level):
            raise TypeError(f"Unexpected value received for: `{permission=}`")

        try:
            return self.get_user_permission(user=user)._level >= permission  # noqa: SLF001
        except ObjectDoesNotExist:
            return False

    def _has_team_permission(self, team: SurveyTeam, permission) -> bool:
        from speleodb.surveys.models.permission_team import TeamPermission

        if not isinstance(permission, TeamPermission.Level):
            raise TypeError(f"Unexpected value received for: `{permission=}`")

        try:
            return self.get_team_permission(team=team)._level >= permission  # noqa: SLF001
        except ObjectDoesNotExist:
            return False

    def _has_permission(self, target: User | SurveyTeam, permission) -> bool:
        if isinstance(target, User):
            return self._has_user_permission(user=target, permission=permission)
        if isinstance(target, SurveyTeam):
            return self._has_user_permission(team=target, permission=permission)
        raise TypeError(f"Unexpected value received for: `{target=}`")

    def has_write_access(self, user: User) -> bool:
        from speleodb.surveys.models.permission_team import TeamPermission
        from speleodb.surveys.models.permission_user import UserPermission

        user_permission = self._has_user_permission(
            user, permission=UserPermission.Level.READ_AND_WRITE
        )

        if user_permission:
            return True

        for team in user.teams:
            if self._has_team_permission(
                team, permission=TeamPermission.Level.READ_AND_WRITE
            ):
                return True

        return False

    def is_admin(self, user: User) -> bool:
        from speleodb.surveys.models.permission_user import UserPermission

        return self._has_user_permission(user, permission=UserPermission.Level.ADMIN)

    @property
    def git_repo_dir(self):
        return (settings.DJANGO_GIT_PROJECTS_DIR / str(self.id)).resolve()

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
    def commit_history(self) -> list[GitCommit]:
        try:
            commits = [
                commit
                for commit in GitlabManager.get_commit_history(project_id=self.id)
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
    def formats(self) -> list[Format]:
        return self.rel_formats.all().order_by("_format")

    @property
    def formats_downloadable(self) -> list[Format]:
        from speleodb.surveys.models import Format

        return [
            _format
            for _format in self.formats
            if _format.raw_format not in Format.FileFormat.__excluded_download_formats__
        ]
