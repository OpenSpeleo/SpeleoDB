#!/usr/bin/env python
# -*- coding: utf-8 -*-

import decimal
import functools
import uuid
import zipfile

import git
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from speleodb.users.models import User
from speleodb.utils.gitlab_manager import GitlabManager

GIT_COMMITTER = git.Actor("SpeleoDB", "contact@speleodb.com")


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
    longitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        validators=[
            MinValueValidator(decimal.Decimal(-180.0)),
            MaxValueValidator(decimal.Decimal(180.0)),
        ],
    )

    latitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        validators=[
            MinValueValidator(decimal.Decimal(-180.0)),
            MaxValueValidator(decimal.Decimal(180.0)),
        ],
    )

    # MUTEX Management
    mutex_owner = models.ForeignKey(
        User,
        related_name="active_mutexes",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        default=None,
    )

    mutex_dt = models.DateTimeField(null=True, blank=True, default=None)

    def __str__(self) -> str:
        return self.name

    def __repsr__(self) -> str:
        return (
            f"<{self.__class__.__name__}: {self.name} "
            f"[{'LOCKED' if self.mutex_owner is not None else 'UNLOCKED'}]> "
            f"Owner: {self.owner.email}"
        )

    def acquire_mutex(self, user: User):
        if not self.has_write_access(user):
            raise PermissionError(f"User: `{user.email} can not execute this action.`")

        # if the user is already the mutex_owner, just refresh the mutex_dt
        # => re-acquire mutex
        if self.mutex_owner is not None and self.mutex_owner != user:
            raise ValidationError(
                "Another user already is currently editing this file: "
                f"{self.mutex_owner}"
            )

        self.mutex_owner = user
        self.mutex_dt = timezone.localtime()
        self.save()

    def release_mutex(self, user):
        if not self.has_write_access(user):
            raise PermissionError(f"User: `{user.email} can not execute this action.`")

        if self.mutex_owner is None:
            # if nobody owns the project, returns without error.
            return

        if self.mutex_owner != user and not self.is_owner(user):
            raise PermissionError(
                f"User: `{user.email} is not the current editor of the project.`"
            )

        self.mutex_owner = None
        self.mutex_dt = None
        self.save()

    def get_date(self):
        return self.when.strftime("%Y/%m/%d %H:%M")

    def get_shortdate(self):
        return self.when.strftime("%Y/%m/%d")

    def get_permission(self, user: User) -> str:
        return self.rel_permissions.get(project=self, user=user)

    def has_write_access(self, user: User):
        from speleodb.surveys.model_files.permission import Permission

        return self.get_permission(user=user).level >= Permission.Level.READ_AND_WRITE

    def is_owner(self, user: User):
        from speleodb.surveys.model_files.permission import Permission

        return self.get_permission(user=user).level >= Permission.Level.OWNER

    @functools.cached_property
    def project_dir(self):
        project_dir = settings.GIT_PROJECTS_DIR / str(self.id)

        if not project_dir.exists():
            project_dir.mkdir(exist_ok=True, parents=True)
            GitlabManager.create_project(self.id)
        return project_dir

    def process_uploaded_file(self, file, user, commit_msg):
        with zipfile.ZipFile(file) as zip_archive:
            data_xml_f = zip_archive.read("Data.xml")

        # Create the project folder if needed
        self.project_dir.mkdir(exist_ok=True, parents=True)

        with (self.project_dir / "Data.xml").open(mode="wb") as f:
            f.write(data_xml_f)

        git_repo = git.Repo(self.project_dir)

        # Add every file pending
        git_repo.index.add("*")

        # If there are modified files:
        if git_repo.is_dirty():
            author = git.Actor(user.name, user.email)
            commit = git_repo.index.commit(
                commit_msg, author=author, committer=GIT_COMMITTER
            )
            git_repo.git.push("--set-upstream", "origin", git_repo.active_branch)

            return commit.hexsha

        return None
