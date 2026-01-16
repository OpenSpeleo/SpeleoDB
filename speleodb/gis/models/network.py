# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from django.db import models

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models.utils import generate_random_token
from speleodb.users.models import User

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise

logger = logging.getLogger(__name__)


class SurfaceMonitoringNetwork(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    # Station identification
    name = models.CharField(
        max_length=100,
        help_text="Monitoring network identifier (e.g., 'A1', 'Network-001')",
    )

    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of the network",
    )

    is_active = models.BooleanField(default=True)

    gis_token = models.CharField(
        "GIS Token",
        max_length=40,
        unique=True,
        blank=False,
        null=False,
        default=generate_random_token,
    )

    # Metadata
    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created or submitted the entry.",
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Surface Monitoring Network"
        verbose_name_plural = "Surface Monitoring Networks"
        indexes = [
            # models.Index(fields=["gis_token"]),  # Present via unique constraint
        ]

    def __str__(self) -> str:
        return f"[Monitoring Network: {self.name}]"

    def refresh_gis_token(self) -> None:
        self.gis_token = generate_random_token()
        self.save()


class SurfaceMonitoringNetworkUserPermission(models.Model):
    user = models.ForeignKey(
        User,
        related_name="network_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    network = models.ForeignKey(
        SurfaceMonitoringNetwork,
        related_name="permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    level = models.IntegerField(
        choices=PermissionLevel.choices_no_webviewer,
        default=PermissionLevel.READ_ONLY,
        null=False,
        blank=False,
    )

    is_active = models.BooleanField(default=True)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    deactivated_by = models.ForeignKey(
        User,
        on_delete=models.RESTRICT,
        blank=True,
        null=True,
        default=None,
    )

    class Meta:
        verbose_name = "Monitoring Network - User Permission"
        verbose_name_plural = "Monitoring Network - User Permissions"
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["network", "is_active"]),
            models.Index(fields=["user", "network", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "network"],
                name="%(app_label)s_%(class)s_user_network_perm_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} => {self.network.name} [{self.level}]"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def deactivate(self, deactivated_by: User) -> None:
        self.is_active = False
        self.deactivated_by = deactivated_by
        self.save()

    def reactivate(self, level: PermissionLevel) -> None:
        self.is_active = True
        self.deactivated_by = None
        self.level = level
        self.save()

    @property
    def level_label(self) -> StrOrPromise:
        return PermissionLevel.from_value(self.level).label
