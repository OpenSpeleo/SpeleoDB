# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
import pathlib
import shutil
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
from django.db.models import IntegerField
from django.db.models import Prefetch
from django.db.models import Q
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce
from django.db.utils import IntegrityError
from django.utils import timezone
from django_countries.fields import CountryField

from git.exc import GitCommandError

from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.exceptions import GitBaseError
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.surveys.models import ProjectType
from speleodb.surveys.models import ProjectVisibility
from speleodb.utils.exceptions import ProjectNotFound
from speleodb.utils.timing_ctx import timed_section

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from datetime import datetime
    from typing import Self

    from speleodb.gis.models import ExplorationLead
    from speleodb.gis.models import ProjectGeoJSON
    from speleodb.gis.models import SubSurfaceStation
    from speleodb.git_engine.core import GitCommit
    from speleodb.surveys.models import Format
    from speleodb.surveys.models import ProjectCommit
    from speleodb.surveys.models import ProjectMutex
    from speleodb.surveys.models import TeamProjectPermission
    from speleodb.surveys.models import UserProjectPermission
    from speleodb.users.models import SurveyTeam
    from speleodb.users.models import User


class ProjectQuerySet(models.QuerySet["Project"]):
    def with_commits(self) -> Self:
        from speleodb.surveys.models import ProjectCommit  # noqa: PLC0415

        latest_commit_qs = ProjectCommit.objects.order_by("-authored_date")

        return self.prefetch_related(
            Prefetch(
                "commits",
                queryset=latest_commit_qs,
                to_attr="_prefetched_commits",
            )
        )

    def with_collaborator_count(self) -> Self:
        from speleodb.surveys.models import TeamProjectPermission  # noqa: PLC0415
        from speleodb.surveys.models import UserProjectPermission  # noqa: PLC0415
        from speleodb.users.models import SurveyTeamMembership  # noqa: PLC0415

        project_table = Project._meta.db_table  # noqa: SLF001
        survey_team_membrshp_table = SurveyTeamMembership._meta.db_table  # noqa: SLF001
        team_proj_perm_table = TeamProjectPermission._meta.db_table  # noqa: SLF001
        user_proj_perm_table = UserProjectPermission._meta.db_table  # noqa: SLF001

        return self.annotate(
            _prefetched_collaborator_count=Coalesce(
                RawSQL(  # noqa: S611
                    f"""
                    SELECT COUNT(*) FROM (
                        SELECT upp.target_id
                        FROM {user_proj_perm_table} upp
                        WHERE upp.project_id = {project_table}.id
                        AND upp.is_active = TRUE

                        UNION

                        SELECT stm.user_id
                        FROM {survey_team_membrshp_table} stm
                        JOIN {team_proj_perm_table} tpp
                        ON tpp.target_id = stm.team_id
                        WHERE tpp.project_id = {project_table}.id
                        AND tpp.is_active = TRUE
                        AND stm.is_active = TRUE
                    ) u
                    """,  # noqa: S608
                    [],
                ),
                0,
                output_field=IntegerField(),
            )
        )

    def with_commit_count(self) -> Self:
        return self.annotate(
            _prefetched_commit_count=Coalesce(models.Count("commits"), 0)
        )

    def with_active_mutex(self) -> Self:
        from speleodb.surveys.models import ProjectMutex  # noqa: PLC0415

        active_mutex_qs = ProjectMutex.objects.filter(is_active=True).select_related(
            "user"
        )

        return self.prefetch_related(
            Prefetch(
                "mutexes",
                queryset=active_mutex_qs,
                to_attr="_prefetched_active_mutex",
            )
        )

    # def with_user_permissions(self) -> Self:
    #     from speleodb.surveys.models import UserProjectPermission

    #     user_permissions_qs = (
    #         UserProjectPermission.objects.filter(is_active=True)
    #         .select_related("target")
    #         .order_by("-level", "target__email")
    #     )

    #     return self.prefetch_related(
    #         Prefetch(
    #             "user_permissions",
    #             queryset=user_permissions_qs,
    #             to_attr="_prefetched_user_permissions",
    #         )
    #     )

    # def with_team_permissions(self) -> Self:
    #     from speleodb.surveys.models import TeamProjectPermission

    #     team_permissions_qs = (
    #         TeamProjectPermission.objects.filter(is_active=True)
    #         .select_related("target")
    #         .order_by("-level", "target__name")
    #     )

    #     return self.prefetch_related(
    #         Prefetch(
    #             "team_permissions",
    #             queryset=team_permissions_qs,
    #             to_attr="_prefetched_team_permissions",
    #         )
    #     )


class Project(models.Model):
    _formats: models.QuerySet[Format]
    _team_permissions: models.QuerySet[TeamProjectPermission]
    _user_permissions: models.QuerySet[UserProjectPermission]

    commits: models.QuerySet[ProjectCommit]
    exploration_leads: models.QuerySet[ExplorationLead]
    geojsons: models.QuerySet[ProjectGeoJSON]
    mutexes: models.QuerySet[ProjectMutex]
    stations: models.QuerySet[SubSurfaceStation]

    # Prefetched attributes
    _prefetched_active_mutex: list[ProjectMutex]
    _prefetched_commits: list[ProjectCommit]
    _prefetched_commit_count: int

    # Automatic fields
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

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

    type = models.CharField(
        max_length=20,
        choices=ProjectType.choices,
        null=False,
        blank=False,
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

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    objects = ProjectQuerySet.as_manager()

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
        indexes = [
            models.Index(fields=["country"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["longitude", "latitude"]),
            models.Index(fields=["visibility"]),
            # models.Index(fields=["target", "project"]), # Present via unique constraint  # noqa: E501
        ]

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__}: {self.name} "
            f"[{'LOCKED' if self.active_mutex is not None else 'UNLOCKED'}]> "
        )

    def __str__(self) -> str:
        return self.name

    @property
    def mutex_owner(self) -> User | None:
        if (active_mutex := self.active_mutex) is None:
            return None

        return active_mutex.user

    @property
    def mutex_dt(self) -> datetime | None:
        if (active_mutex := self.active_mutex) is None:
            return None
        return active_mutex.modified_date

    @property
    def latest_commit(self) -> ProjectCommit | None:
        if hasattr(self, "_prefetched_commits"):
            return self._prefetched_commits[0] if self._prefetched_commits else None
        return self.commits.order_by("-authored_date").first()

    def _active_mutex(self) -> ProjectMutex | None:
        if hasattr(self, "_prefetched_active_mutex"):
            return (
                self._prefetched_active_mutex[0]
                if self._prefetched_active_mutex
                else None
            )

        return self.mutexes.filter(is_active=True).select_related("user").first()

    @property
    def active_mutex(self) -> ProjectMutex | None:
        return self._active_mutex()

    @property
    def commit_count(self) -> int:
        try:
            return self._prefetched_commit_count
        except AttributeError:
            return self.commits.count()

    def acquire_mutex(self, user: User) -> None:
        if not self.has_write_access(user):
            raise PermissionError(f"User: `{user.email} can not execute this action.`")

        # if the user is already the mutex_owner, just refresh the mutex_dt
        # => re-acquire mutex
        if (active_mutex := self.active_mutex) is not None:
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

    def release_mutex(self, user: User, comment: str = "") -> None:
        if (active_mutex := self.active_mutex) is None:
            # if nobody owns the project, returns without error.
            return

        if self.mutex_owner != user and not self.has_admin_access(user):
            raise PermissionError(f"User: `{user.email} can not execute this action.`")

        # AutoSave in the background
        active_mutex.release_mutex(user=user, comment=comment)

    def get_best_permission(
        self, user: User
    ) -> TeamProjectPermission | UserProjectPermission:
        return user.get_best_permission(project=self)

    def get_user_permission(self, user: User) -> UserProjectPermission:
        return self._user_permissions.get(target=user, is_active=True)

    def get_team_permission(self, team: SurveyTeam) -> TeamProjectPermission:
        return self._team_permissions.get(target=team, is_active=True)

    @property
    def user_permissions(self) -> models.QuerySet[UserProjectPermission]:
        return (
            self._user_permissions.filter(is_active=True)
            .select_related("target")
            .order_by("-level", "target__email")
        )

    @property
    def team_permissions(self) -> models.QuerySet[TeamProjectPermission]:
        return (
            self._team_permissions.filter(is_active=True)
            .select_related("target")
            .order_by("-level", "target__name")
        )

    @property
    def permissions(self) -> chain[TeamProjectPermission | UserProjectPermission]:
        return chain(self.user_permissions, self.team_permissions)

    @property
    def user_permission_count(self) -> int:
        return self._user_permissions.filter(is_active=True).count()

    @property
    def team_permission_count(self) -> int:
        return self._team_permissions.filter(is_active=True).count()

    @property
    def collaborator_count(self) -> int:
        if hasattr(self, "_prefetched_collaborator_count"):
            return self._prefetched_collaborator_count  # type: ignore[no-any-return]

        from speleodb.surveys.models import UserProjectPermission  # noqa: PLC0415
        from speleodb.users.models import SurveyTeamMembership  # noqa: PLC0415

        direct_user_ids = UserProjectPermission.objects.filter(
            project=self,
            is_active=True,
        ).values_list("target", flat=True)

        team_user_ids = SurveyTeamMembership.objects.filter(
            team__project_permissions__project=self,
            team__project_permissions__is_active=True,
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
        git_repo = self.git_repo
        hexsha = git_repo.commit_and_push_project(
            message=message, author_name=author.name, author_email=author.email
        )

        # Ensure the git history is properly constructed
        self.construct_git_history_from_project(git_repo=git_repo)

        return hexsha

    def checkout_commit_or_default_pull_branch(self, hexsha: str | None = None) -> None:
        if not (git_repo := self.git_repo):
            raise ProjectNotFound("This project does not exist on gitlab or on drive")

        try:
            if hexsha is None:
                # Make sure the project is update to ToT (Top of Tree)
                git_repo.checkout_default_branch_and_pull()
            else:
                git_repo.checkout_commit(hexsha=hexsha)

        except (GitBaseError, GitCommandError):
            logger.warning(
                "Failed to checkout/pull for project %s. "
                "Deleting local copy and re-cloning from scratch.",
                self.id,
            )

            # Delete the corrupted/broken local repository
            shutil.rmtree(self.git_repo_dir, ignore_errors=True)

            # Re-clone from scratch (git_repo property handles this when the
            # directory doesn't exist)
            git_repo = self.git_repo

            # Retry once with the fresh clone
            if hexsha is None:
                git_repo.checkout_default_branch_and_pull()
            else:
                git_repo.checkout_commit(hexsha=hexsha)

        self.construct_git_history_from_project(git_repo=git_repo)

    def construct_git_history_from_project(self, git_repo: GitRepo) -> None:
        from speleodb.surveys.models import ProjectCommit  # noqa: PLC0415

        with timed_section("Constructing Git History"):
            hashtable = {
                commit.id: commit
                for commit in ProjectCommit.objects.filter(project=self)
            }

            # 1. Get all commits from HEAD
            commits: list[GitCommit] = list(git_repo.iter_commits("HEAD"))

            # 2. Sort by commit datetime (oldest first)
            commits.sort(key=lambda c: c.committed_date)

            # 3. Rebuild commits in order
            for git_commit in commits:
                if git_commit.hexsha not in hashtable:
                    # Ignore errors silently and proceed
                    with contextlib.suppress(IntegrityError):
                        _ = ProjectCommit.get_or_create_from_commit(
                            project=self,
                            commit=git_commit,
                        )

    @property
    def formats(self) -> models.QuerySet[Format]:
        return self._formats.all()

    @property
    def formats_downloadable(self) -> list[Format]:
        from speleodb.surveys.models import FileFormat  # noqa: PLC0415

        return [
            _format
            for _format in self.formats
            if _format.raw_format not in FileFormat.__excluded_download_formats__
        ]

    def refresh_geojson(self) -> None:
        """Refresh the GeoJSON data for this project."""
        # This method will be implemented by the refresh_project_geojson task
        # to populate the geojson field
        raise NotImplementedError
