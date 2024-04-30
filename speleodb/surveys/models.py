#!/usr/bin/env python
# -*- coding: utf-8 -*-

import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from speleodb.users.models import User


class Project(models.Model):
    # Automatic fields
    id = models.AutoField(primary_key=True)
    creation_date = models.DateTimeField(auto_now_add=True, editable=False)

    owner = models.ForeignKey(User, related_name="projects", on_delete=models.RESTRICT)

    # User Definable
    fork_from = models.ForeignKey(
        "self", related_name="fork", on_delete=models.RESTRICT, null=True, default=None
    )

    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    # Automatically Defined
    longitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    latitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    git_name = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        blank=False,
        null=False,
        unique=True,
    )
    mutex_owner = models.ForeignKey(
        User,
        related_name="active_mutexes",
        on_delete=models.RESTRICT,
        null=True,
    )
    mutex_dt = models.DateTimeField(default=None, null=True)

    def __str__(self):
        return self.name

    def acquire_mutex(self, user: User):
        if self.mutex_owner is not None:
            raise ValidationError(
                "Another user already is currently editing this file: "
                f"{self.mutex_owner}"
            )
        self.mutex_owner = user
        self.mutex_dt = timezone.localtime()
        self.save()

    def release_mutex(self):
        if self.mutex_owner is None:
            raise ValidationError("No user is currently editing this file")
        self.mutex_owner = None
        self.mutex_dt = None
        self.save()

    def get_date(self):
        return self.when.strftime("%Y/%m/%d %H:%M")

    def get_shortdate(self):
        return self.when.strftime("%Y/%m/%d")


class AccessRight(models.Model):
    project = models.ForeignKey(
        Project,
        related_name="project",
        on_delete=models.CASCADE,
    )

    user = models.ForeignKey(User, related_name="user", on_delete=models.CASCADE)

    class AccessType(models.TextChoices):
        READ_ONLY = ("RO", "READ_ONLY")
        READ_AND_WRITE = ("RW", "READ_AND_WRITE")
        ADMIN = ("AD", "ADMIN")

    right = models.CharField(
        max_length=2,
        choices=AccessType.choices,
        default=AccessType.READ_ONLY,
    )

    def __str__(self):
        return f"{self.user} => {self.project} [{self.right}]"
