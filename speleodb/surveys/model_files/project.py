#!/usr/bin/env python
# -*- coding: utf-8 -*-

import decimal
import pathlib
import shutil
import uuid
import zipfile

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django_countries.fields import CountryField

from speleodb.users.models import User
from speleodb.utils.exceptions import ProjectNotFound
from speleodb.utils.gitlab_manager import GitlabManager
from speleodb.utils.gitlab_manager import GitRepo

TML_XML_FILENAME = "Data.xml"
TML_DEFAULT_FILENAME = "project.tml"


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

    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)

    country = CountryField()

    # Optional Field
    fork_from = models.ForeignKey(
        "self",
        related_name="forks",
        on_delete=models.RESTRICT,
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
            MinValueValidator(decimal.Decimal(-180.0)),
            MaxValueValidator(decimal.Decimal(180.0)),
        ],
    )

    longitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(decimal.Decimal(-180.0)),
            MaxValueValidator(decimal.Decimal(180.0)),
        ],
    )

    class Visibility(models.IntegerChoices):
        PRIVATE = (0, "PRIVATE")
        PUBLIC = (1, "PUBLIC")

    _visibility = models.IntegerField(
        choices=Visibility.choices,
        verbose_name="visibility",
        default=Visibility.PRIVATE,
    )

    class Software(models.IntegerChoices):
        MANUAL = (0, "MANUAL")
        ARIANE = (1, "ARIANE")
        COMPASS = (2, "COMPASS")
        WALLS = (3, "WALLS")
        STICKMAPS = (4, "STICKMAPS")
        OTHER = (99, "OTHER")

    _software = models.IntegerField(choices=Software.choices, verbose_name="software")

    # MUTEX Management
    active_mutex = models.OneToOneField(
        "Mutex",
        related_name="rel_active_mutexed_project",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        default=None,
    )

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if self.active_mutex and self.active_mutex.project != self:
            raise ValueError(
                f"Mutex Project mismatch: {self.active_mutex.project=} && {self=}"
            )
        super().save(*args, **kwargs)

    @property
    def software(self) -> str:
        return self.Software(self._software).label

    @software.setter
    def software(self, value):
        self._software = value

    @property
    def visibility(self) -> str:
        return self.Visibility(self._visibility).label

    @visibility.setter
    def visibility(self, value):
        self._visibility = value

    @property
    def mutex_owner(self):
        try:
            return self.active_mutex.user
        except AttributeError:
            return None

    @property
    def mutex_dt(self):
        try:
            return self.active_mutex.last_modified_dt
        except AttributeError:
            return None

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__}: {self.name} "
            f"[{'LOCKED' if self.active_mutex is not None else 'UNLOCKED'}]> "
        )

    def acquire_mutex(self, user: User):
        if not self.has_write_access(user):
            raise PermissionError(f"User: `{user.email} can not execute this action.`")

        # if the user is already the mutex_owner, just refresh the mutex_dt
        # => re-acquire mutex
        if self.mutex_owner is not None:
            if self.mutex_owner != user:
                raise ValidationError(
                    "Another user already is currently editing this file: "
                    f"{self.mutex_owner}"
                )
            self.active_mutex.last_modified_dt = timezone.localtime()
            self.active_mutex.save()
        else:
            from speleodb.surveys.models import Mutex

            self.active_mutex = Mutex.objects.create(project=self, user=user)
            self.save()

    def release_mutex(self, user: User, comment: str = ""):
        if self.active_mutex is None:
            # if nobody owns the project, returns without error.
            return

        if self.mutex_owner != user and not self.is_owner(user):
            raise PermissionError(f"User: `{user.email} can not execute this action.`")

        # AutoSave in the background
        self.active_mutex.release_mutex(user=user, comment=comment)

    def get_date(self):
        return self.when.strftime("%Y/%m/%d %H:%M")

    def get_shortdate(self):
        return self.when.strftime("%Y/%m/%d")

    def get_permission(self, user: User) -> str:
        return self.rel_permissions.get(user=user, is_active=True)

    def get_all_permissions(self):
        return self.rel_permissions.filter(is_active=True)

    def get_permission_count(self):
        return self.rel_permissions.filter(is_active=True).count()

    def _has_permission(self, user: User, permission):
        from speleodb.surveys.model_files.permission import Permission

        if not isinstance(permission, Permission.Level):
            raise TypeError(f"Unexpected value received for: `{permission=}`")

        try:
            return self.get_permission(user=user)._level >= permission  # noqa: SLF001
        except ObjectDoesNotExist:
            return False

    def has_write_access(self, user: User):
        from speleodb.surveys.model_files.permission import Permission

        return self._has_permission(user, permission=Permission.Level.READ_AND_WRITE)

    def is_owner(self, user: User):
        from speleodb.surveys.model_files.permission import Permission

        return self._has_permission(user, permission=Permission.Level.OWNER)

    # @functools.cached_property
    @property
    def git_repo(self):
        project_dir = (settings.DJANGO_GIT_PROJECTS_DIR / str(self.id)).resolve()

        if not project_dir.exists():
            git_repo = GitlabManager.create_or_clone_project(self.id)
            git_repo_path = pathlib.Path(git_repo).resolve()

            if project_dir != git_repo_path:
                raise ValueError(
                    f"Difference detected between `{git_repo_path=}` "
                    f"and `{project_dir=}`"
                )
            return git_repo

        return GitRepo(project_dir)

    def process_uploaded_file(self, file, user, commit_msg):
        with zipfile.ZipFile(file) as zip_archive:
            data_xml_f = zip_archive.read(TML_XML_FILENAME)

        # Make sure the project is update to ToT (Top of Tree)
        self.git_repo.checkout_and_pull()

        with (self.git_repo.path / TML_XML_FILENAME).open(mode="wb") as f:
            f.write(data_xml_f)

        return self.git_repo.commit_and_push_project(message=commit_msg, user=user)

    @property
    def commit_history(self):
        commits = GitlabManager.get_commit_history(project_id=self.id)
        if isinstance(commits, (list, tuple)):
            return commits
        return []

    def generate_tml_file(self, commit_sha1=None):
        if not self.git_repo:
            raise ProjectNotFound("This project does not exist on gitlab or on drive")

        if commit_sha1 is None:
            # Make sure the project is update to ToT (Top of Tree)
            self.git_repo.checkout_branch_or_commit(branch_name="master")
            self.git_repo.pull()

        else:
            self.git_repo.checkout_branch_or_commit(commit_sha1=commit_sha1)

        dest_dir = settings.DJANGO_TMP_DL_DIR / self.git_repo.commit_sha1

        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_dir.mkdir(exist_ok=True, parents=True)

        tml_file = dest_dir / TML_DEFAULT_FILENAME

        with zipfile.ZipFile(tml_file, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            for file in self.git_repo.path.glob("*"):
                if not file.is_file() or file.name.startswith("."):
                    continue

                zipf.write(file, file.relative_to(self.git_repo.path))

        return tml_file
