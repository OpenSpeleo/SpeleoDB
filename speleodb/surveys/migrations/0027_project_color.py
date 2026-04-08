# -*- coding: utf-8 -*-

from __future__ import annotations

import random

from django.db import migrations
from django.db import models

import speleodb.common.enums

# Hardcoded snapshot of ColorPalette.COLORS at migration time for reproducibility
PALETTE = (
    "#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00",
    "#ffff33", "#a65628", "#f781bf", "#999999", "#66c2a5",
    "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854", "#ffd92f",
    "#e5c494", "#b3b3b3", "#1b9e77", "#d95f02", "#7570b3",
)


def assign_random_colors(apps, schema_editor):
    """Assign a random color to every existing project."""
    Project = apps.get_model("surveys", "Project")
    for project in Project.objects.all():
        project.color = random.choice(PALETTE)  # noqa: S311
        project.save(update_fields=["color"])


class Migration(migrations.Migration):
    dependencies = [
        ("surveys", "0026_unique_together_update"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="color",
            field=models.CharField(
                default=speleodb.common.enums.ColorPalette.random_color,
                help_text="Hex color code for map rendering (e.g. #e41a1c)",
                max_length=7,
            ),
        ),
        migrations.RunPython(
            assign_random_colors,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
