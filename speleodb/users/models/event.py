"""For security reasons and accountability, we record login & logout events."""

from __future__ import annotations

from django.db import models

from speleodb.common.enums import UserAction
from speleodb.common.enums import UserApplication
from speleodb.users.models.user import User


class AccountEvent(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_index=True,
        verbose_name="user",
        related_name="event_history",
    )

    ip_addr = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name="IP Address",
    )

    user_agent = models.TextField(blank=True)

    action = models.CharField(
        max_length=20,
        choices=UserAction.choices,
        blank=False,
    )

    application = models.CharField(
        max_length=20,
        choices=UserApplication.choices,
        blank=True,
        default="",
    )

    # Timestamps
    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Account Event"
        verbose_name_plural = "Account Events"
        ordering = ["-creation_date"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["ip_addr"]),
            models.Index(fields=["action"]),
            models.Index(fields=["application"]),
            models.Index(fields=["creation_date"]),
        ]

    def __str__(self) -> str:
        return f"[{self.application}] {self.user} => {self.action}"
