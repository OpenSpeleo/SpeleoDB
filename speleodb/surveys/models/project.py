# -*- coding: utf-8 -*-

from __future__ import annotations

import pathlib
import uuid
from itertools import chain
from typing import TYPE_CHECKING
from typing import Any

from cachetools import TTLCache
from cachetools import cached
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
from speleodb.utils.django_base_models import BaseIntegerChoices
from speleodb.utils.exceptions import ProjectNotFound

if TYPE_CHECKING:
    import datetime

    from speleodb.gis.models import ProjectGeoJSON
    from speleodb.gis.models import Station
    from speleodb.surveys.models import Format
    from speleodb.surveys.models import ProjectMutex
    from speleodb.surveys.models import TeamProjectPermission
    from speleodb.surveys.models import UserProjectPermission
    from speleodb.users.models import SurveyTeam
    from speleodb.users.models import User


class ProjectVisibility(BaseIntegerChoices):
    PRIVATE = (0, "PRIVATE")
    PUBLIC = (1, "PUBLIC")


class Project(models.Model):
    # type checking
    rel_formats: models.QuerySet[Format]
    rel_geojsons: models.QuerySet[ProjectGeoJSON]
    rel_mutexes: models.QuerySet[ProjectMutex]
    rel_user_permissions: models.QuerySet[UserProjectPermission]
    rel_team_permissions: models.QuerySet[TeamProjectPermission]
    rel_stations: models.QuerySet[Station]

    # Automatic fields
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )
    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    name = models.CharField(max_length=255, blank=False, null=False)
    description = models.TextField(blank=False, null=False)

    country = CountryField(null=False, blank=False)

    exclude_geojson = models.BooleanField(
        default=False,
        help_text="Exclude GeoJSON from the project",
        blank=False,
        null=False,
    )

    # Optional Field
    fork_from = models.ForeignKey(
        "self",
        related_name="forks",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        default=None,
    )

    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created or submitted the entry.",
    )

    # Geo Coordinates
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )

    visibility = models.IntegerField(
        choices=ProjectVisibility.choices,
        blank=False,
        null=False,
        default=ProjectVisibility.PRIVATE,
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Is Active",
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
            f"[{'LOCKED' if self.active_mutex() is not None else 'UNLOCKED'}]> "
        )

    def __str__(self) -> str:
        return self.name

    @cached(cache=TTLCache(maxsize=1, ttl=300))
    def active_mutex(self) -> ProjectMutex | None:
        try:
            return self.rel_mutexes.filter(is_active=True).select_related("user")[0]
        except IndexError:
            return None

    @property
    def mutex_owner(self) -> User | None:
        if (active_mutex := self.active_mutex()) is None:
            return None

        return active_mutex.user

    @property
    def mutex_dt(self) -> datetime.datetime | None:
        if (active_mutex := self.active_mutex()) is None:
            return None
        return active_mutex.modified_date

    def acquire_mutex(self, user: User) -> None:
        if not self.has_write_access(user):
            raise PermissionError(f"User: `{user.email} can not execute this action.`")

        # if the user is already the mutex_owner, just refresh the mutex_dt
        # => re-acquire mutex
        if (active_mutex := self.active_mutex()) is not None:
            if active_mutex.user != user:
                raise ValidationError(
                    "Another user already is currently editing this file: "
                    f"{active_mutex.user}"
                )
            active_mutex.modified_date = timezone.localtime()
            active_mutex.save()

        else:
            from speleodb.surveys.models import ProjectMutex  # noqa: PLC0415

            _ = ProjectMutex.objects.create(project=self, user=user)

        self.void_mutex_cache()

    def release_mutex(self, user: User, comment: str = "") -> None:
        if (active_mutex := self.active_mutex()) is None:
            # if nobody owns the project, returns without error.
            return

        if self.mutex_owner != user and not self.has_admin_access(user):
            raise PermissionError(f"User: `{user.email} can not execute this action.`")

        # AutoSave in the background
        active_mutex.release_mutex(user=user, comment=comment)

        self.void_mutex_cache()

    def get_best_permission(
        self, user: User
    ) -> TeamProjectPermission | UserProjectPermission:
        return user.get_best_permission(project=self)

    def get_user_permission(self, user: User) -> UserProjectPermission:
        return self.rel_user_permissions.get(target=user, is_active=True)

    def get_team_permission(self, team: SurveyTeam) -> TeamProjectPermission:
        return self.rel_team_permissions.get(target=team, is_active=True)

    @property
    def user_permissions(self) -> models.QuerySet[UserProjectPermission]:
        return (
            self.rel_user_permissions.filter(is_active=True)
            .select_related("target")
            .order_by("-level", "target__email")
        )

    @property
    def team_permissions(self) -> models.QuerySet[TeamProjectPermission]:
        return (
            self.rel_team_permissions.filter(is_active=True)
            .select_related("target")
            .order_by("-level", "target__name")
        )

    @property
    def permissions(self) -> chain[TeamProjectPermission | UserProjectPermission]:
        return chain(self.user_permissions, self.team_permissions)

    @property
    def user_permission_count(self) -> int:
        return self.rel_user_permissions.filter(is_active=True).count()

    @property
    def team_permission_count(self) -> int:
        return self.rel_team_permissions.filter(is_active=True).count()

    @property
    def collaborator_count(self) -> int:
        from speleodb.surveys.models import UserProjectPermission  # noqa: PLC0415
        from speleodb.users.models import SurveyTeamMembership  # noqa: PLC0415

        direct_user_ids = UserProjectPermission.objects.filter(
            project=self,
            is_active=True,
        ).values_list("target", flat=True)

        team_user_ids = SurveyTeamMembership.objects.filter(
            team__rel_permissions__project=self,
            team__rel_permissions__is_active=True,
            is_active=True,
        ).values_list("user", flat=True)

        return direct_user_ids.union(team_user_ids).count()

    def has_write_access(self, user: User) -> bool:
        from speleodb.common.enums import PermissionLevel  # noqa: PLC0415

        return user.get_best_permission(self).level >= PermissionLevel.READ_AND_WRITE

    def has_admin_access(self, user: User) -> bool:
        from speleodb.common.enums import PermissionLevel  # noqa: PLC0415

        try:
            return self.get_user_permission(user=user).level >= PermissionLevel.ADMIN
        except ObjectDoesNotExist:
            return False

    @property
    def git_repo_dir(self) -> pathlib.Path:
        return pathlib.Path(settings.DJANGO_GIT_PROJECTS_DIR / str(self.id)).resolve()

    @property
    def git_repo(self) -> GitRepo:
        for _ in range(settings.DJANGO_GIT_RETRY_ATTEMPTS):
            if not self.git_repo_dir.exists():
                git_repo = GitlabManager.create_or_clone_project(self)
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
                commit_history := GitlabManager.get_commit_history(project=self)
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

    def void_mutex_cache(self) -> None:
        self.active_mutex.cache_clear()
