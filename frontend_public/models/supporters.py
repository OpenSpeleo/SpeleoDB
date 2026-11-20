from __future__ import annotations

import uuid

from django.core.validators import URLValidator
from django.db import models
from django.db.models.functions import Lower

from speleodb.utils.s3_storages import OrganizationLogoStorage
from speleodb.utils.validators import ImageWithHeicSupportValidator


class BaseSupporter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    order = models.IntegerField(
        blank=True,
        null=True,
        help_text="Lower numbers appear first. Leave blank to list by name afterward.",
    )

    class Meta:
        abstract = True
        ordering = [models.F("order").asc(nulls_last=True), "name", "pk"]

    def __str__(self) -> str:
        return self.name


class OrganizationSupporter(BaseSupporter):
    website = models.URLField(validators=[URLValidator(schemes=["http", "https"])])
    logo = models.ImageField(
        upload_to="supporters/organizations/",
        storage=OrganizationLogoStorage(),
        validators=[
            ImageWithHeicSupportValidator(
                allowed_extensions=["jpg", "jpeg", "png", "webp"]
            )
        ],
        help_text="Logo of the organization (JPEG, PNG, or WebP format)",
    )

    class Meta(BaseSupporter.Meta):
        verbose_name = "Supporting Organization"
        verbose_name_plural = "Supporting Organizations"


class PersonSupporter(BaseSupporter):
    website = models.URLField(
        blank=True,
        validators=[URLValidator(schemes=["http", "https"])],
    )

    class Meta(BaseSupporter.Meta):
        ordering = [Lower("name"), "name", "pk"]
        verbose_name = "Supporting Person"
        verbose_name_plural = "Supporting People"
