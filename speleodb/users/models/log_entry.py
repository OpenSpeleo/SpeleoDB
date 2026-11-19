"""Permanent snapshots of explicit administrator actions."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

import django.contrib.admin.models
from django.contrib.admin.utils import quote
from django.db import models
from django.urls import NoReverseMatch
from django.urls import reverse
from django.utils import timezone

if TYPE_CHECKING:
    from speleodb.users.models import User


class LogEntry(models.Model):
    class Action(models.IntegerChoices):
        ADDITION = 1, "Addition"
        CHANGE = 2, "Change"
        DELETION = 3, "Deletion"
        ACTION = 4, "Action"

    action_time = models.DateTimeField(default=timezone.now, editable=False)
    actor_email = models.EmailField()
    model_label = models.CharField(max_length=255, blank=True)
    # Preserve native history's distinction between unknown and empty targets.
    object_id = models.TextField(blank=True, null=True)  # noqa: DJ001
    object_repr = models.CharField(max_length=200)
    action_flag = models.PositiveSmallIntegerField(choices=Action.choices)
    change_message = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "log entry"
        verbose_name_plural = "log entries"
        ordering = ["-action_time", "-id"]
        indexes = [
            models.Index(fields=["-action_time", "-id"], name="admin_audit_time_idx"),
            models.Index(
                fields=["actor_email", "-action_time"], name="admin_audit_actor_idx"
            ),
            models.Index(
                fields=["model_label", "object_id"], name="admin_audit_object_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_action_flag_display()}: {self.object_repr}"

    @classmethod
    def for_admin_user(cls, user: User) -> models.QuerySet[LogEntry]:
        """Keep campaign audit snapshots private across admin history surfaces."""
        entries = cls.objects.all()
        if not user.is_superuser:
            entries = entries.exclude(model_label__startswith="campaigns.")
        return entries

    @classmethod
    def record(
        cls,
        *,
        actor_email: str,
        action_flag: int,
        obj: models.Model | None = None,
        change_message: str | list[dict[str, Any]] = "",
        details: dict[str, Any] | None = None,
        model_label: str = "",
        object_repr: str = "",
    ) -> LogEntry:
        return cls.objects.create(
            actor_email=actor_email,
            action_flag=action_flag,
            model_label=obj._meta.label_lower if obj is not None else model_label,  # noqa: SLF001
            object_id=str(obj.pk) if obj is not None else None,
            object_repr=(str(obj) if obj is not None else object_repr)[:200],
            change_message=(
                json.dumps(change_message)
                if isinstance(change_message, list)
                else change_message
            ),
            details=details if details is not None else {},
        )

    def is_addition(self) -> bool:
        return self.action_flag == self.Action.ADDITION

    def is_change(self) -> bool:
        return self.action_flag == self.Action.CHANGE

    def is_deletion(self) -> bool:
        return self.action_flag == self.Action.DELETION

    def get_change_message(self) -> str:
        # Reuse Django's pure structured-message formatter, without accessing
        # its table or retaining a dependency on its user/content-type relations.
        try:
            return django.contrib.admin.models.LogEntry(
                change_message=self.change_message
            ).get_change_message()
        except AttributeError, KeyError, TypeError:
            # Historical messages were editable free text. Preserve malformed
            # structured values for the templates to render with normal escaping.
            return self.change_message

    def get_admin_url(self) -> str | None:
        if not self.model_label or not self.object_id:
            return None
        app_label, separator, model_name = self.model_label.partition(".")
        if not separator:
            return None
        try:
            return reverse(
                f"admin:{app_label}_{model_name}_change", args=[quote(self.object_id)]
            )
        except NoReverseMatch:
            return None
