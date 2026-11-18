# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
import math
import pathlib
import re
import shutil
import uuid
from collections import defaultdict
from collections import deque
from dataclasses import asdict
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from itertools import chain
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from typing import Any

import compass_lib.geojson
import orjson
from compass_lib.geojson import project_to_geojson
from compass_lib.interface import CompassInterface
from compass_lib.loop_closure.presets import InverseLengthWeightedL1SpatialSolver
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.core.validators import RegexValidator
from django.db import models
from django.db import transaction
from django.db.models import IntegerField
from django.db.models import Prefetch
from django.db.models import Q
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce
from django.db.utils import IntegrityError
from django.utils import timezone
from django_countries.fields import CountryField
from openspeleo_lib.enums import ArianeShotType
from openspeleo_lib.errors import EmptySurveyError
from openspeleo_lib.geojson import NoKnownAnchorError
from openspeleo_lib.geojson import survey_to_geojson
from openspeleo_lib.interfaces import ArianeInterface
from openspeleo_lib.interfaces import StalagmightInterface
from openspeleo_lib.loop_closure.presets import (
    InverseLengthWeightedConjugateGradientHorizontalSolver,
)
from openspeleo_lib.loop_closure.presets import (
    LengthAzimuthWeightedLeastSquaresHorizontalSolver,
)

from speleodb.background_jobs.archive_sources import mirror_project
from speleodb.background_jobs.archive_sources import project_git_source
from speleodb.common.constants import EXPLORATION_LEAD_MAX_HEADINGS
from speleodb.common.constants import HEADING_FULL_CIRCLE
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
from speleodb.utils.gps_utils import format_coordinate
from speleodb.utils.s3_storages import GeoJSONStorage
from speleodb.utils.timing_ctx import timed_section

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from typing import Any
    from typing import Self

    import openspeleo_lib

    from speleodb.gis.models import ExplorationLead
    from speleodb.gis.models import ExplorationLeadSource
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

LEAD_CARDINALS = {
    name: index * 22.5
    for index, name in enumerate(
        (
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        )
    )
}
LEAD_MARKER = re.compile(r"!(" + "|".join(LEAD_CARDINALS) + r"|[0-9]+)!")


@dataclass(frozen=True)
class ResolvedSurveyShot:
    """Native observation and its original destination after map conversion."""

    uuid: str | None
    shot_id: str
    from_id: str
    namespace: tuple[str, ...]
    length_m: float | None
    azimuth: float | None
    comment: str | None
    longitude: float
    latitude: float


@dataclass(frozen=True)
class GeoJSONBuildResult:
    geojson: dict[str, Any]
    shots: tuple[ResolvedSurveyShot, ...]


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
    exploration_lead_sources: models.QuerySet[ExplorationLeadSource]
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
    description = models.TextField(blank=True, null=False)

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

    def checkout_commit_or_reset_default_branch(
        self, hexsha: str | None = None
    ) -> None:
        git_repo = self.git_repo
        self.ensure_git_origin(git_repo)
        if hexsha is None:
            git_repo.reset_default_branch_to_remote()
            # Complete traversal before reconciling the rebuildable history cache.
            # Historical checkouts must not remove newer remote revisions.
            reachable: list[str] = [
                commit.hexsha for commit in git_repo.iter_commits("HEAD")
            ]
            with transaction.atomic():
                self.construct_git_history_from_project(git_repo=git_repo)
                self.commits.exclude(pk__in=reachable).delete()
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

    @staticmethod
    def exploration_headings(comment: str | None) -> list[float]:
        """Take up to three distinct valid directions, ignoring malformed markers."""
        headings: list[float] = []
        for match in LEAD_MARKER.finditer((comment or "").upper()):
            token = match.group(1)
            heading = LEAD_CARDINALS.get(token)
            if heading is None and token.isascii() and token.isdigit():
                # Strip padding before conversion so even a very long invalid token
                # cannot exceed Python's integer-input limit or abort conversion.
                digits = token.lstrip("0") or "0"
                if len(digits) <= len(str(HEADING_FULL_CIRCLE)):
                    value = int(digits)
                    if value < HEADING_FULL_CIRCLE:
                        heading = float(value)
            if heading is not None and heading not in headings:
                headings.append(heading)
                if len(headings) == EXPLORATION_LEAD_MAX_HEADINGS:
                    break
        return headings

    def _lead_signatures(
        self,
        shot: ResolvedSurveyShot,
    ) -> list[tuple[int, str, Any]]:
        """UUID payloads are unscoped; the database lookup always scopes the project."""
        payloads: list[tuple[int, Any]] = []
        if shot.uuid is not None:
            payloads.append(
                (
                    self.exploration_lead_sources.model.Kind.UUID,
                    str(uuid.UUID(shot.uuid)),
                )
            )
        namespace = [self.type, *shot.namespace]
        payloads.append(
            (
                self.exploration_lead_sources.model.Kind.ENDPOINTS,
                [namespace, shot.shot_id, shot.from_id],
            )
        )
        if shot.length_m is not None and shot.azimuth is not None:
            if math.isfinite(shot.length_m) and math.isfinite(shot.azimuth):
                length = Decimal(str(shot.length_m))
                azimuth = Decimal(str(shot.azimuth % 360))
                payloads.append(
                    (
                        self.exploration_lead_sources.model.Kind.MEASUREMENT,
                        [
                            namespace,
                            shot.shot_id,
                            format(length.normalize(), "f"),
                            format(azimuth.normalize(), "f"),
                        ],
                    )
                )
        return [
            (kind, sha256(orjson.dumps(payload)).hexdigest(), payload)
            for kind, payload in payloads
        ]

    @transaction.atomic
    def sync_exploration_leads(
        self,
        commit: ProjectCommit,
        shots: list[ResolvedSurveyShot] | tuple[ResolvedSurveyShot, ...],
    ) -> None:
        """Import new sources and learn aliases without changing existing leads."""
        # Bypass prefetched history: a queued conversion may have become historical.
        if not shots or commit.project_id != self.pk:
            return
        # Git timestamps can tie or run backwards. A recorded descendant always
        # supersedes its ancestors, regardless of when metadata was reconstructed.
        parent_ids = {
            parent
            for parents in self.commits.order_by().values_list("parent_ids", flat=True)
            for parent in parents
        }
        if (
            self.commits.exclude(pk__in=parent_ids).values_list("pk", flat=True).first()
            != commit.pk
        ):
            return
        candidates = [(shot, self._lead_signatures(shot)) for shot in shots]
        digests = {
            digest for _, signatures in candidates for _, digest, _ in signatures
        }
        if not digests:
            return
        sources = {
            (source.kind, source.digest): source
            for source in self.exploration_lead_sources.filter(
                digest__in=digests
            ).select_related("lead")
        }
        signature_members: dict[tuple[int, str], list[int]] = defaultdict(list)
        payloads: dict[tuple[int, str], Any] = {}
        candidate_keys: list[list[tuple[int, str]]] = []
        for index, (_, signatures) in enumerate(candidates):
            keys: list[tuple[int, str]] = []
            for kind, digest, payload in signatures:
                key = (kind, digest)
                existing = sources.get(key)
                if (existing is not None and existing.payload != payload) or (
                    key in payloads and payloads[key] != payload
                ):
                    raise ValueError("Exploration lead signature digest collision.")
                payloads[key] = payload
                signature_members[key].append(index)
                keys.append(key)
            candidate_keys.append(keys)

        def connected_groups(
            keys_by_candidate: list[list[tuple[int, str]]], maximum_kind: int
        ) -> list[list[int]]:
            """Visit each observation and signature once per priority pass."""
            groups: list[list[int]] = []
            visited: set[int] = set()
            expanded: set[tuple[int, str]] = set()
            for index in range(len(candidates)):
                if index in visited:
                    continue
                group: list[int] = []
                pending = deque([index])
                visited.add(index)
                while pending:
                    current = pending.popleft()
                    group.append(current)
                    for key in keys_by_candidate[current]:
                        if key[0] > maximum_kind or key in expanded:
                            continue
                        expanded.add(key)
                        for neighbor in signature_members[key]:
                            if neighbor not in visited:
                                visited.add(neighbor)
                                pending.append(neighbor)
                groups.append(group)
            return groups

        # Deletion propagates before any new UUID or endpoint can claim a live
        # owner. A chain of current aliases cannot resurrect a deleted source.
        deleted: set[int] = set()
        deleted_keys: set[tuple[int, str]] = set()
        suppressed_leads: set[uuid.UUID] = set()
        for group in connected_groups(
            candidate_keys, self.exploration_lead_sources.model.Kind.MEASUREMENT
        ):
            group_keys = {key for index in group for key in candidate_keys[index]}
            matches = [sources[key] for key in group_keys if key in sources]
            if any(source.lead_id is None for source in matches):
                deleted.update(group)
                deleted_keys.update(group_keys)
                suppressed_leads.update(
                    source.lead_id for source in matches if source.lead_id is not None
                )

        # Persisted signatures never change owner. Only unclaimed signatures can
        # transmit a newly learned identity, and never at a stronger priority than
        # the evidence that established it. Three bounded graph passes preserve
        # known UUID owners when weaker endpoint signatures connect their shots.
        unclaimed_keys = [
            [key for key in keys if key not in sources] for keys in candidate_keys
        ]
        assignments: dict[int, tuple[int, uuid.UUID | None]] = {}
        groups: list[list[int]] = []
        for priority in self.exploration_lead_sources.model.Kind.values:
            groups = connected_groups(unclaimed_keys, priority)
            for group in groups:
                owners: set[uuid.UUID] = set()
                ambiguous = False
                for index in group:
                    if index in deleted:
                        continue
                    if index in assignments:
                        owner = assignments[index][1]
                        if owner is None:
                            ambiguous = True
                        else:
                            owners.add(owner)
                    else:
                        matches = [
                            sources[key]
                            for key in candidate_keys[index]
                            if key in sources and key[0] <= priority
                        ]
                        if matches:
                            owner = min(matches, key=lambda source: source.kind).lead_id
                            assert owner is not None
                            owners.add(owner)
                if ambiguous or owners:
                    owner = (
                        next(iter(owners))
                        if len(owners) == 1 and not ambiguous
                        else None
                    )
                    for index in group:
                        if index not in deleted and index not in assignments:
                            assignments[index] = (priority, owner)

        leads: dict[uuid.UUID, ExplorationLead] = {
            source.lead_id: source.lead
            for source in sources.values()
            if source.lead_id is not None and source.lead is not None
        }
        new_leads: dict[uuid.UUID, ExplorationLead] = {}
        coordinates = [
            (
                Decimal(str(format_coordinate(shot.longitude))),
                Decimal(str(format_coordinate(shot.latitude))),
            )
            for shot, _ in candidates
        ]
        for group in groups:
            if any(index in deleted or index in assignments for index in group):
                continue
            if len({coordinates[index] for index in group}) != 1:
                logger.warning(
                    "Conflicting exploration lead destinations in project %s "
                    "for a new source",
                    self.pk,
                )
                continue
            annotated = [
                index
                for index in group
                if self.exploration_headings(candidates[index][0].comment)
            ]
            if not annotated:
                continue
            # Duplicate native observations at one location must select the same
            # initial comment even when conversion traverses them in reverse.
            selected = min(
                annotated,
                key=lambda index: (
                    candidates[index][0].shot_id,
                    candidates[index][0].from_id,
                    candidates[index][0].uuid or "",
                    candidates[index][0].namespace,
                    candidates[index][0].comment or "",
                ),
            )
            shot = candidates[selected][0]
            lead = self.exploration_leads.model(
                project=self,
                description=shot.comment or "",
                directions=[
                    {"heading": heading, "checked": False}
                    for heading in self.exploration_headings(shot.comment)
                ],
                created_by=commit.author_email or self.created_by,
            )
            leads[lead.pk] = new_leads[lead.pk] = lead
            for index in group:
                assignments[index] = (
                    self.exploration_lead_sources.model.Kind.MEASUREMENT,
                    lead.pk,
                )

        # Check destinations before learning aliases, so equally strong
        # contradictory observations cannot claim a new source identity.
        destinations: dict[uuid.UUID, tuple[int, tuple[Decimal, Decimal]]] = {}
        conflicts: set[uuid.UUID] = set()
        for index, (priority, owner) in assignments.items():
            if owner is None:
                logger.warning(
                    "Conflicting exploration lead identities in project %s",
                    self.pk,
                )
                continue
            previous = destinations.get(owner)
            if previous is None or priority < previous[0]:
                destinations[owner] = (priority, coordinates[index])
                conflicts.discard(owner)
            elif priority == previous[0] and coordinates[index] != previous[1]:
                conflicts.add(owner)
        for owner, (_, destination) in destinations.items():
            if owner in conflicts:
                logger.warning(
                    "Conflicting exploration lead destinations "
                    "in project %s for lead %s",
                    self.pk,
                    owner,
                )
                continue
            if owner in suppressed_leads:
                continue
            if owner in new_leads:
                lead = new_leads[owner]
                lead.longitude, lead.latitude = destination
        pending_sources: list[ExplorationLeadSource] = []
        for key, members in signature_members.items():
            if key in sources:
                continue
            source_lead: ExplorationLead | None = None
            if key not in deleted_keys:
                source_owners = {
                    assignments[index][1] if index in assignments else None
                    for index in members
                }
                if len(source_owners) != 1 or None in source_owners:
                    continue
                owner = next(iter(source_owners))
                assert owner is not None
                if owner in conflicts or owner in suppressed_leads:
                    continue
                source_lead = leads[owner]
            pending_sources.append(
                self.exploration_lead_sources.model(
                    project=self,
                    lead=source_lead,
                    kind=key[0],
                    digest=key[1],
                    payload=payloads[key],
                    source_format=self.type,
                )
            )
        self.exploration_leads.model.objects.bulk_create(list(new_leads.values()))
        self.exploration_lead_sources.model.objects.bulk_create(pending_sources)

    def convert_geojson_history(
        self,
        git_repo: GitRepo,
        directory: pathlib.Path,
        *,
        force_recompute: bool = False,
        revision: str | None = None,
    ) -> ConversionSummary:
        """Continue conversion failures, preserving old artifacts until replacement."""
        # Even an unusable HEAD must supersede historical annotations. Establish
        # the complete ancestry before publishing any successfully converted source.
        self.construct_git_history_from_project(git_repo)
        head_revision = git_repo.head.commit.hexsha
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
                    result = self.build_geojson(source)
                    record = self.commits.model.get_or_create_from_commit(
                        project=self, commit=commit
                    )
                    replace_project_geojson(
                        self,
                        record,
                        result.geojson,
                        replace_existing=force_recompute,
                        source_shots=result.shots
                        if commit.hexsha == head_revision
                        else (),
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

    def build_geojson(self, file: pathlib.Path) -> GeoJSONBuildResult:
        """Export using the source software's native loop-closure preset."""
        if not self.supports_geojson:
            raise GeoJSONGenerationError(
                f"This project type is not supported yet: `{self.type}`."
            )
        shots: list[ResolvedSurveyShot] = []
        data: dict[str, Any]

        def collect(
            shot: compass_lib.ResolvedShot | openspeleo_lib.ResolvedShot,
        ) -> None:
            shots.append(ResolvedSurveyShot(**asdict(shot)))

        try:
            match self.type:
                case ProjectType.COMPASS:
                    data = project_to_geojson(
                        CompassInterface.load_project(file),
                        include_stations=False,
                        include_legs=True,
                        include_passages=False,
                        include_anchors=True,
                        color_by_origin=False,
                        loop_closure=InverseLengthWeightedL1SpatialSolver,
                        on_resolved_shot=collect,
                    )
                    return GeoJSONBuildResult(data, tuple(shots))
                case ProjectType.ARIANE:
                    survey = ArianeInterface.from_file(file)
                    solver = InverseLengthWeightedConjugateGradientHorizontalSolver
                case ProjectType.STALAGMIGHT:
                    survey = StalagmightInterface.from_file(file)
                    solver = LengthAzimuthWeightedLeastSquaresHorizontalSolver
                case _:
                    # Unsupported types were rejected before conversion began.
                    raise AssertionError(self.type)  # noqa: TRY301
            # Keep expected omissions as skips before native preparation, whose
            # missing-control validation otherwise raises a generic ValueError.
            stations = [
                shot
                for shot in survey.shots
                if not shot.excluded and shot.shot_type != ArianeShotType.CLOSURE
            ]
            if not stations:
                raise EmptySurveyError(  # noqa: TRY301 - expected omission
                    "The survey has no active stations."
                )
            if not any(shot.is_geolocation_known() for shot in stations):
                raise NoKnownAnchorError(  # noqa: TRY301 - expected omission
                    "The survey has no usable geographic anchor."
                )
            data = survey_to_geojson(
                survey, loop_closure_solver=solver, on_resolved_shot=collect
            )
            return GeoJSONBuildResult(data, tuple(shots))
        except (
            EmptySurveyError,
            NoKnownAnchorError,
            compass_lib.geojson.NoKnownAnchorError,
        ):
            raise
        except Exception as error:
            reraise_task_timeout(error)
            logger.exception("Error processing %s survey file `%s`.", self.type, file)
            raise GeoJSONGenerationError from error
