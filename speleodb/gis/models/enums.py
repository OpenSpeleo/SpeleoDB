# -*- coding: utf-8 -*-

from __future__ import annotations

from django.db import models


class InstallStatus(models.TextChoices):
    INSTALLED = "installed", "Installed"
    RETRIEVED = "retrieved", "Retrieved"
    LOST = "lost", "Lost"
    ABANDONED = "abandoned", "Abandoned"


class OperationalStatus(models.TextChoices):
    FUNCTIONAL = "functional", "Functional"
    BROKEN = "broken", "Broken"
    LOST = "lost", "Lost"
    ABANDONED = "abandoned", "Abandoned"


class UnitSystem(models.TextChoices):
    METRIC = "metric", "Metric"
    IMPERIAL = "imperial", "Imperial"
