import uuid

from django.db import models


class MonitoringNetwork(models.Model):
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

    # Metadata
    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created or submitted the entry.",
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[Network: {self.name}]"
