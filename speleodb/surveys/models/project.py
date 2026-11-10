# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
import pathlib
import shutil
import uuid
from dataclasses import asdict
from dataclasses import dataclass
from itertools import chain
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from typing import Any

import compass_lib.geojson
from compass_lib.geojson import project_to_geojson
from compass_lib.interface import CompassInterface
from compass_lib.solver.sparse import SparseSolver
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import IntegerField
from django.db.models import Prefetch
from django.db.models import Q
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce
from django.db.utils import IntegrityError
from django.utils import timezone
from django_countries.fields import CountryField
from openspeleo_lib.errors import EmptySurveyError
from openspeleo_lib.geojson import NoKnownAnchorError
from openspeleo_lib.geojson import survey_to_geojson
from openspeleo_lib.interfaces import ArianeInterface
from openspeleo_lib.interfaces import StalagMightInterface

from speleodb.background_jobs.archive_sources import mirror_project
from speleodb.background_jobs.archive_sources import project_git_source
from speleodb.common.enums import ColorPalette
from speleodb.common.enums import ProjectType
from speleodb.common.enums import ProjectVisibility
from speleodb.gis.geojson_sources import materialize_geojson_source
from speleodb.gis.geojson_workspaces import geojson_workspace
from speleodb.gis.project_geojson_services import replace_project_geojson
from speleodb.git_engine.core import GitRepo
from speleodb.git_engine.gitlab_manager import GitlabCredentials
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.utils.exceptions import GeoJSONGenerationError
from speleodb.utils.exceptions import reraise_task_timeout
from speleodb.utils.s3_storages import GeoJSONStorage
from speleodb.utils.timing_ctx import timed_section

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from typing import Any
    from typing import Self

    from openspeleo_lib.models import Survey

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

logger = logging.getLogger(__name__)


@dataclass
class ConversionSummary:
    processed: int = 0
    generated: int = 0
    existing: int = 0
    skipped: int = 0
    failed: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConversionFailedError(Exception):
    """At least one revision failed; independent revisions were still processed."""

    def __init__(self, summary: ConversionSummary | dict[str, Any]) -> None:
        self.summary = (
            summary
            if isinstance(summary, ConversionSummary)
            else ConversionSummary(**summary)
        )
        # Celery reconstructs JSON failures from Exception.args. A primitive
        # summary also survives its pickleability probe without a wrapper.
        super().__init__(self.summary.as_dict())

    def __str__(self) -> str:
        return f"Map conversion failed for {self.summary.failed} revision(s)."


class ProjectQuerySet(models.QuerySet["Project"]):
    def with_commits(self) -> Self:
        from speleodb.surveys.models import ProjectCommit  # noqa: PLC0415

        latest_commit_qs = ProjectCommit.objects.all()

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

    color = models.CharField(
        max_length=7,
        default=ColorPalette.random_color,
        validators=[
            RegexValidator(r"^#[0-9a-fA-F]{6}$", "Must be a #RRGGBB hex color")
        ],
        help_text="Hex color code for map rendering (e.g. #e41a1c)",
    )

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
        return self.commits.first()

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

    @property
    def git_repo_dir(self) -> pathlib.Path:
        root = pathlib.Path(settings.DJANGO_GIT_PROJECTS_DIR).resolve()
        candidate = root / str(uuid.UUID(str(self.pk)))
        if candidate.is_symlink() or candidate.resolve().parent != root:
            raise RuntimeError("The project checkout path is unsafe.")
        return candidate

    def discard_checkout(self) -> None:
        """Remove only this project's validated UUID-owned checkout."""
        path = self.git_repo_dir
        if path.exists():
            if not path.is_dir():
                raise RuntimeError("The project checkout is not a directory.")
            shutil.rmtree(path)

    @property
    def git_repo(self) -> GitRepo:
        """Open the local repository, or acquire it when no checkout exists."""
        path = self.git_repo_dir
        repository = (
            GitRepo.from_directory(path)
            if path.exists()
            else GitlabManager.create_or_clone_project(self)
        )
        if repository is None:
            raise RuntimeError("The project repository is unavailable.")
        return repository

    def reset_failed_upload_checkout(self) -> None:
        """Reset local files without cloning or querying a failed transaction."""
        path = self.git_repo_dir
        if path.is_dir():
            repository = GitRepo(path)
            repository.reset_and_remove_untracked()

    def purge_geojsons(self) -> int:
        """Delete all immutable keys in precisely this project's storage namespace."""
        storage = GeoJSONStorage()
        prefix = storage.object_key(f"{self.pk}/")
        if not prefix.endswith("/"):
            prefix += "/"
        client: Any = storage.connection.meta.client
        deleted = 0
        for page in client.get_paginator("list_objects_v2").paginate(
            Bucket=storage.bucket_name, Prefix=prefix
        ):
            objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
            if not objects:
                continue
            if any(not obj["Key"].startswith(prefix) for obj in objects):
                raise RuntimeError(
                    "Storage returned an object outside the project namespace."
                )
            result = client.delete_objects(
                Bucket=storage.bucket_name, Delete={"Objects": objects, "Quiet": True}
            )
            if result.get("Errors"):
                raise RuntimeError("Some project GeoJSON objects could not be deleted.")
            deleted += len(objects)
        remaining = client.list_objects_v2(
            Bucket=storage.bucket_name, Prefix=prefix, MaxKeys=1
        )
        if remaining.get("Contents"):
            raise RuntimeError(
                "The project GeoJSON namespace is not empty after deletion."
            )
        return deleted

    def reset_git_history(
        self,
        *,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Rebuild Git history and purge maps; the caller regenerates eligible maps."""
        notify = progress or (lambda _stage: None)
        notify("validate_remote")
        # Read and materialize the existing remote before any deletion. This does
        # not call create_or_clone_project, which can initialize absent repositories.
        with geojson_workspace(prefix="history-reset-") as directory:
            source = project_git_source(
                self.pk, has_recorded_history=self.commits.exists()
            )
            # Keep supervised Git children in a private workspace. A hard-killed
            # worker cannot finish Python cleanup, and its supervisor may still be
            # stopping Git when an operator starts manual recovery. Those children
            # must never continue writing the canonical checkout.
            fresh_checkout = directory / "replacement"
            fresh = mirror_project(
                source,
                fresh_checkout,
                heartbeat=lambda: notify("validate_remote"),
            )
            if fresh.state != "mirrored" or fresh.used_fallback_head:
                raise RuntimeError(
                    "The existing remote has no default-branch history to rebuild."
                )
            repository = GitRepo(fresh_checkout)
            # Mirror acquisition removes its service remote and transient
            # credentials. Restore only a plain origin; ordinary checkout
            # access applies the established authenticated-origin policy.
            repository.create_remote("origin", source.url)
            notify("delete_history")
            self.commits.all().delete()
            notify("purge_geojsons")
            deleted = self.purge_geojsons()
            notify("discard_checkout")
            self.discard_checkout()
            notify("install_checkout")
            target = self.git_repo_dir
            if target.exists():
                raise RuntimeError(
                    "The project checkout changed during history reconstruction."
                )
            # All clone/checkout commands have completed.
            # shutil.move also supports a scratch root on a different filesystem.
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(fresh_checkout), str(target))
            repository = GitRepo(target)
            # A fresh clone owns the remote's default branch, including the
            # initial commit; history rebuilding must not filter it out.
            notify("rebuild_history")
            self.construct_git_history_from_project(repository)
            expected_commits = {
                commit.hexsha for commit in repository.iter_commits("HEAD")
            }
            recorded_commits = set(self.commits.values_list("id", flat=True))
            if recorded_commits != expected_commits:
                raise RuntimeError(
                    "The complete Git history could not be reconstructed."
                )
            result: dict[str, Any] = {
                "project_id": str(self.pk),
                "commits": self.commits.count(),
                "deleted_objects": deleted,
                "geojson_skipped": self.exclude_geojson or not self.supports_geojson,
            }
            notify("history_rebuilt")
            return result

    @property
    def commit_history(self) -> list[dict[str, Any]] | None:
        if (commit_history := GitlabManager.get_commit_history(project=self)) is None:
            return []
        return [
            commit
            for commit in commit_history
            if commit["message"] != settings.DJANGO_GIT_FIRST_COMMIT_MESSAGE
        ]

    def has_write_access(self, user: User) -> bool:
        from speleodb.common.enums import PermissionLevel  # noqa: PLC0415

        return user.get_best_permission(self).level >= PermissionLevel.READ_AND_WRITE

    def has_admin_access(self, user: User) -> bool:
        from speleodb.common.enums import PermissionLevel  # noqa: PLC0415

        try:
            return self.get_user_permission(user=user).level >= PermissionLevel.ADMIN
        except ObjectDoesNotExist:
            return False

    def commit_and_push_project(self, message: str, author: User) -> str | None:
        git_repo = self.git_repo
        hexsha = git_repo.commit_and_push_project(
            message=message, author_name=author.name, author_email=author.email
        )

        # Ensure the git history is properly constructed
        self.construct_git_history_from_project(git_repo=git_repo)
        return hexsha

    def checkout_commit_or_default_pull_branch(self, hexsha: str | None = None) -> None:
        git_repo = self.git_repo
        self.ensure_git_origin(git_repo)
        if hexsha is None:
            git_repo.checkout_default_branch_and_pull()
        else:
            git_repo.checkout_commit(hexsha=hexsha)
        self.construct_git_history_from_project(git_repo=git_repo)

    def ensure_git_origin(self, git_repo: GitRepo) -> None:
        # Configuration drift is repairable without deleting local work. Network
        # and checkout failures are not evidence of repository corruption.
        origin = git_repo.remotes.origin
        expected_url = GitlabCredentials.get().project_url(self.id)
        if origin.url != expected_url:
            git_repo.set_origin_url(expected_url)

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

    @property
    def supports_geojson(self) -> bool:
        """Whether the project software has an existing GeoJSON exporter."""
        return self.type in {
            ProjectType.ARIANE,
            ProjectType.COMPASS,
            ProjectType.STALAGMIGHT,
        }

    def convert_geojson_history(
        self,
        git_repo: GitRepo,
        directory: pathlib.Path,
        *,
        force_recompute: bool = False,
        revision: str | None = None,
    ) -> ConversionSummary:
        """Continue conversion failures, preserving old artifacts until replacement."""
        summary = ConversionSummary()
        first_error: Exception | None = None
        commits = (
            [git_repo.commit(revision)]
            if revision is not None
            else git_repo.iter_commits("HEAD")
        )
        for commit in commits:
            summary.processed += 1
            if (
                not force_recompute
                and self.geojsons.filter(commit_id=commit.hexsha).exists()
            ):
                summary.existing += 1
                continue
            try:
                with TemporaryDirectory(prefix="sources-", dir=directory) as temporary:
                    source = materialize_geojson_source(
                        self, commit, pathlib.Path(temporary)
                    )
                    if source is None:
                        summary.skipped += 1
                        logger.info(
                            "Skipping GeoJSON for project %s at commit %s: "
                            "missing source",
                            self.pk,
                            commit.hexsha,
                        )
                        continue
                    data = self.build_geojson(source)
                    record = self.commits.model.get_or_create_from_commit(
                        project=self, commit=commit
                    )
                    replace_project_geojson(
                        self,
                        record,
                        data,
                        replace_existing=force_recompute,
                    )
                    summary.generated += 1
            except NoKnownAnchorError, compass_lib.geojson.NoKnownAnchorError:
                summary.skipped += 1
                logger.info(
                    "Skipping GeoJSON for project %s at commit %s: "
                    "no usable GPS anchor",
                    self.pk,
                    commit.hexsha,
                )
            except EmptySurveyError:
                summary.skipped += 1
                logger.info(
                    "Skipping GeoJSON for project %s at commit %s: empty survey",
                    self.pk,
                    commit.hexsha,
                )
            except Exception as error:
                reraise_task_timeout(error)
                summary.failed += 1
                logger.exception(
                    "GeoJSON conversion failed for project %s at commit %s",
                    self.pk,
                    commit.hexsha,
                )
                if first_error is None:
                    first_error = error
        if summary.failed:
            raise ConversionFailedError(summary) from first_error
        return summary

    def build_geojsons(
        self,
        *,
        force_recompute: bool = False,
        revision: str | None = None,
    ) -> ConversionSummary:
        """Build GeoJSONs from a read-only clone for CLI and worker callers."""
        if self.exclude_geojson or not self.supports_geojson:
            raise ValueError(
                "This project is excluded or has no supported GeoJSON exporter."
            )
        with geojson_workspace(prefix="rebuild-") as directory:
            repository = directory / "repository"
            mirrored = mirror_project(
                project_git_source(self.pk, has_recorded_history=self.commits.exists()),
                repository,
                heartbeat=lambda: None,
            )
            if mirrored.state != "mirrored":
                return ConversionSummary()
            git_repo = GitRepo(repository)
            return self.convert_geojson_history(
                git_repo,
                directory,
                force_recompute=force_recompute,
                revision=revision,
            )

    def build_geojson(self, file: pathlib.Path) -> dict[str, Any]:
        """Build the GeoJSON from the survey file on disk."""
        interface: type[ArianeInterface | StalagMightInterface]
        match self.type:
            case ProjectType.ARIANE:
                interface = ArianeInterface
            case ProjectType.STALAGMIGHT:
                interface = StalagMightInterface
            case ProjectType.COMPASS:
                try:
                    project = CompassInterface.load_project(file)
                    return project_to_geojson(
                        project,
                        include_stations=False,
                        include_legs=True,
                        include_passages=False,
                        include_anchors=True,
                        color_by_origin=False,
                        solver=SparseSolver(),
                    )

                except compass_lib.geojson.NoKnownAnchorError:
                    raise

                except FileNotFoundError as e:
                    logger.error(f"File does not exists `{file}`.")  # noqa: TRY400
                    raise GeoJSONGenerationError from e

                except Exception as e:
                    reraise_task_timeout(e)
                    logger.error(  # noqa: TRY400
                        f"Error processing file `{file}`. Not a valid Compass Project"
                    )
                    raise GeoJSONGenerationError from e

            case _:
                raise GeoJSONGenerationError(
                    f"This project type is not supported yet: `{self.type}`."
                )

        try:
            survey: Survey = interface.from_file(file)
            return survey_to_geojson(survey)

        except EmptySurveyError, NoKnownAnchorError:
            raise

        except Exception as e:
            reraise_task_timeout(e)
            logger.error(f"Error processing {self.type} survey file `{file}`.")  # noqa: TRY400
            raise GeoJSONGenerationError from e
