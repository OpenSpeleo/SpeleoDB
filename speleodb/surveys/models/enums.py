# -*- coding: utf-8 -*-

from __future__ import annotations

from django.db import models

from speleodb.utils.django_base_models import BaseIntegerChoices


class ProjectType(models.TextChoices):
    ARIANE = "ariane", "ARIANE"
    COMPASS = "compass", "COMPASS"
    STICKMAPS = "stickmaps", "STICKMAPS"
    THERION = "therion", "THERION"
    WALLS = "walls", "WALLS"
    OTHER = "other", "OTHER"


class ProjectVisibility(BaseIntegerChoices):
    PRIVATE = (0, "PRIVATE")
    PUBLIC = (1, "PUBLIC")
