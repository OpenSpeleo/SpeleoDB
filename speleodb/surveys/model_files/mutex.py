#!/usr/bin/env python
# -*- coding: utf-8 -*-

import django.utils.timezone
from django.db import models
from model_utils import FieldTracker

from speleodb.surveys.models import Project
from speleodb.users.models import User


class Mutex(models.Model):
    project = models.ForeignKey(
        Project,
        related_name="rel_mutexes",
        on_delete=models.CASCADE,
    )

    user = models.ForeignKey(
        User, related_name="rel_mutexes", on_delete=models.RESTRICT
    )

    creation_dt = models.DateTimeField(auto_now_add=True, editable=False)
    heartbeat_dt = models.DateTimeField(auto_now=True, editable=False)

    closing_user = models.ForeignKey(
        User,
        related_name="rel_closing_mutexes",
        on_delete=models.RESTRICT,
        blank=True,
        null=True,
        default=None,
    )
    closing_dt = models.DateTimeField(
        null=True, blank=True, default=None, editable=False
    )
    closing_comment = models.TextField(blank=True, default="")

    closing_tracker = FieldTracker(fields=["closing_user"])

    class Meta:
        verbose_name_plural = "mutexes"

    def __str__(self):
        return f"{self.user} => {self.project} @ {self.creation_dt}"

    def save(self, *args, **kwargs):
        if self.closing_tracker.changed():
            self.closing_dt = django.utils.timezone.now()

        super().save(*args, **kwargs)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def release_mutex(self, user: User, comment: str):
        self.closing_user = user
        self.closing_comment = comment
        self.save()

        mutexed_project = self.rel_active_mutexed_project
        mutexed_project.active_mutex = None
        mutexed_project.save()
