#!/usr/bin/env python
# -*- coding: utf-8 -*-

import decimal
import pathlib
import shutil
import uuid
import zipfile

from django.conf import settings
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

    # @functools.cached_property
    @property
    def git_repo(self):
        project_dir = settings.DJANGO_GIT_PROJECTS_DIR / str(self.id)

        if not project_dir.exists():
            git_repo = GitlabManager.create_or_clone_project(self.id)
            if project_dir != pathlib.Path(git_repo):
                raise ValueError(
                    f"Difference detected between `{pathlib.Path(git_repo)=}` "
                    f"and `{project_dir=}`"
                )
            return git_repo

        return GitRepo(project_dir)

    def process_uploaded_file(self, file, user, commit_msg):
        with zipfile.ZipFile(file) as zip_archive:
            data_xml_f = zip_archive.read(TML_XML_FILENAME)

        # Make sure the project is update to ToT (Top of Tree)
        self.git_repo.pull()

        with (self.git_repo.path / TML_XML_FILENAME).open(mode="wb") as f:
            f.write(data_xml_f)

        return self.git_repo.commit_and_push_project(message=commit_msg, user=user)

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
                print(f"[*] processing: `{file}`: ", end="")
                if not file.is_file() or file.name.startswith("."):
                    print("SKIPPED")
                    continue

                print(f"[*] ADDED => `{file.relative_to(self.git_repo.path)}`")
                zipf.write(file, file.relative_to(self.git_repo.path))

        return tml_file
