"""Install only this application's schedules; Railway never schedules them."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django_celery_beat.models import IntervalSchedule
from django_celery_beat.models import PeriodicTask


class Command(BaseCommand):
    help = "Idempotently install the background-job Celery Beat schedules."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        schedules: tuple[tuple[str, str, int], ...] = (
            (
                "project-geojson-dispatch",
                "speleodb.gis.tasks.dispatch_project_geojsons",
                60,
            ),
            (
                "background-job-maintenance",
                "speleodb.background_jobs.tasks.maintain_background_jobs",
                60,
            ),
            (
                "export-artifact-cleanup",
                "speleodb.background_jobs.tasks.delete_expired_artifacts",
                300,
            ),
            ("celery.backend_cleanup", "celery.backend_cleanup", 86400),
        )
        for name, task, seconds in schedules:
            interval, _ = IntervalSchedule.objects.get_or_create(
                every=seconds, period=IntervalSchedule.SECONDS
            )
            PeriodicTask.objects.update_or_create(
                name=name,
                defaults={
                    "task": task,
                    "interval": interval,
                    "crontab": None,
                    "solar": None,
                    "clocked": None,
                    "queue": "background_control",
                    "enabled": True,
                    "args": "[]",
                    "kwargs": "{}",
                    "description": (
                        "Managed by install_background_schedules. Runs in Celery Beat."
                    ),
                },
            )
        self.stdout.write(
            self.style.SUCCESS("Installed background-job Celery Beat schedules.")
        )
