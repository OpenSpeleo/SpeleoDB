"""Exercise the scheduler's isolated runtime in fresh Python interpreters."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
from django.db import connection

from speleodb.testing.database import postgres_test_database_url

REPOSITORY_ROOT: Path = Path(__file__).resolve().parents[2]
BEAT_MEMORY_LIMIT_BYTES: int = 100_000_000


def _run_beat_probe(
    script: str, tmp_path: Path, *, database_url: str | None = None
) -> dict[str, Any]:
    environment: dict[str, str] = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.beat",
            "DJANGO_READ_DOT_ENV_FILE": "false",
            "DJANGO_SECRET_KEY": "isolated-scheduler-runtime-test",
            "DATABASE_URL": database_url or f"sqlite:///{tmp_path / 'beat.sqlite3'}",
            "USE_DOCKER": "false",
            "CELERY_BROKER_URL": "memory://",
        }
    )
    completed: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        [sys.executable, "-c", dedent(script)],
        env=environment,
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result: object = json.loads(completed.stdout)
    assert isinstance(result, dict)
    return result


def test_beat_loader_and_publication_stay_small_and_do_not_import_tasks(
    tmp_path: Path,
) -> None:
    observed: dict[str, Any] = _run_beat_probe(
        """
        import json
        import sys
        from importlib import import_module
        from pathlib import Path

        from django.apps import apps
        from config.celery_app import app

        app.loader.init_worker()
        import_module("speleodb.background_jobs.scheduler")
        result = app.send_task("speleodb.users.tasks.get_users_count")
        with app.connection_for_read() as connection:
            message = connection.SimpleQueue("background_control").get(block=False)
            headers = message.headers
            message.ack()
        status = Path("/proc/self/status").read_text()
        print(json.dumps({
            "apps": [entry.name for entry in apps.get_app_configs()],
            "modules": sorted(sys.modules),
            "threads": int(next(line.split()[1] for line in status.splitlines()
                                if line.startswith("Threads:"))),
            "peak_rss_bytes": int(next(line.split()[1]
                                       for line in status.splitlines()
                                       if line.startswith("VmHWM:"))) * 1024,
            "backend": type(app.backend).__name__,
            "task": headers["task"],
            "ignore_result": headers["ignore_result"],
            "id": headers["id"],
            "sent_id": result.id,
        }))
        """,
        tmp_path,
    )
    assert observed["apps"] == ["django_celery_beat"]
    assert observed["threads"] == 1
    assert observed["peak_rss_bytes"] <= BEAT_MEMORY_LIMIT_BYTES
    assert observed["backend"] == "DisabledBackend"
    assert observed["task"] == "speleodb.users.tasks.get_users_count"
    assert observed["ignore_result"] is False
    assert observed["id"] == observed["sent_id"]
    forbidden_prefixes: tuple[str, ...] = (
        "config.settings.base",
        "config.settings.production",
        "config.urls",
        "django.contrib.admin",
        "django_celery_results",
        "speleodb.users",
        "speleodb.surveys",
        "speleodb.gis",
        "speleodb.background_jobs.tasks",
        "celery.worker.consumer",
        "numpy",
        "scipy",
        "pandas",
        "PIL",
        "sentry_sdk",
    )
    assert not [
        name for name in observed["modules"] if name.startswith(forbidden_prefixes)
    ]


@pytest.mark.django_db(transaction=True)
def test_minimal_scheduler_publishes_housekeeping_policy_without_task_imports(
    tmp_path: Path,
) -> None:
    if connection.vendor != "postgresql":
        pytest.skip("Scheduler ownership requires a real PostgreSQL test database.")
    observed: dict[str, Any] = _run_beat_probe(
        """
        import json
        import sys
        from importlib import import_module

        from celery.beat import ScheduleEntry
        from django.db import connection
        from config.celery_app import app
        from config.task_results import HOUSEKEEPING_TASK_NAMES
        from speleodb.background_jobs.lease import SchedulerLease

        app.loader.init_worker()
        scheduler_module = import_module("speleodb.background_jobs.scheduler")
        names = sorted(HOUSEKEEPING_TASK_NAMES) + [
            "speleodb.users.tasks.get_users_count",
        ]
        lease = SchedulerLease(connection.get_connection_params())
        lease.acquire()
        scheduler = scheduler_module.ExponentialBackoffDatabaseScheduler(
            app=app, lease=lease, lazy=True,
        )
        try:
            for name in names:
                entry = ScheduleEntry(
                    name=name, task=name,
                    options={"queue": "background_control"}, app=app,
                )
                scheduler.apply_async(entry, advance=False)
            with app.connection_for_read() as broker:
                with broker.SimpleQueue("background_control") as queue:
                    messages = []
                    while queue.qsize():
                        message = queue.get(block=False)
                        messages.append(message.headers)
                        message.ack()
        finally:
            scheduler.close()
            lease.close()
        print(json.dumps({
            "messages": messages,
            "tasks": list(app.tasks),
            "modules": sorted(sys.modules),
            "backend": type(app.backend).__name__,
        }))
        """,
        tmp_path,
        database_url=postgres_test_database_url(),
    )
    assert {
        message["task"]: message["ignore_result"] for message in observed["messages"]
    } == {
        "speleodb.gis.tasks.dispatch_project_geojsons": True,
        "speleodb.background_jobs.tasks.maintain_background_jobs": True,
        "speleodb.background_jobs.tasks.delete_expired_artifacts": True,
        "celery.backend_cleanup": True,
        "speleodb.users.tasks.get_users_count": False,
    }
    assert observed["backend"] == "DisabledBackend"
    assert not any(name.startswith("speleodb.") for name in observed["tasks"])
    assert not any(
        name.startswith(("django_celery_results", "speleodb.background_jobs.tasks"))
        for name in observed["modules"]
    )


@pytest.mark.django_db(transaction=True)
def test_minimal_scheduler_preserves_database_schedule_behavior(tmp_path: Path) -> None:
    if connection.vendor != "postgresql":
        pytest.skip("Scheduler ownership requires a real PostgreSQL test database.")
    observed: dict[str, Any] = _run_beat_probe(
        """
        import json
        from datetime import timedelta
        from importlib import import_module

        from django.db import connection
        from django.utils import timezone
        from config.celery_app import app
        from speleodb.background_jobs.lease import SchedulerLease

        app.loader.init_worker()

        models = import_module("django_celery_beat.models")
        CrontabSchedule = models.CrontabSchedule
        IntervalSchedule = models.IntervalSchedule
        PeriodicTask = models.PeriodicTask
        scheduler_module = import_module("speleodb.background_jobs.scheduler")

        now = timezone.now()
        interval = IntervalSchedule.objects.create(every=60, period="seconds")
        for name, enabled, one_off in (
            ("due", True, False),
            ("disabled", False, False),
            ("once", True, True),
        ):
            PeriodicTask.objects.create(
                name=name, task="speleodb.users.tasks.get_users_count",
                interval=interval, enabled=enabled, one_off=one_off,
                last_run_at=now - timedelta(seconds=120),
                queue="background_control",
            )
        cleanup_interval = IntervalSchedule.objects.create(
            every=86400, period="seconds"
        )
        cleanup = PeriodicTask.objects.create(
            name="celery.backend_cleanup", task="celery.backend_cleanup",
            interval=cleanup_interval, last_run_at=now,
            queue="background_control", description="installer owns this schedule",
        )
        cron = CrontabSchedule.objects.create(
            minute="0", hour="*", timezone="America/Cancun",
        )
        PeriodicTask.objects.create(
            name="local-time", task="speleodb.users.tasks.get_users_count",
            crontab=cron, last_run_at=now, start_time=now + timedelta(days=1),
        )
        lease = SchedulerLease(connection.get_connection_params())
        lease.acquire()
        scheduler = scheduler_module.ExponentialBackoffDatabaseScheduler(
            app=app, lease=lease,
        )
        initial_names = sorted(scheduler.schedule)
        cron_timezone = str(scheduler.schedule["local-time"].schedule.tz)
        for _ in range(2):
            scheduler.tick()
        scheduler.sync()
        due = PeriodicTask.objects.get(name="due")
        due_last_run = due.last_run_at >= now
        once = PeriodicTask.objects.get(name="once")
        once_count = once.total_run_count
        once_last_run = once.last_run_at is not None
        scheduler.schedule["once"].is_due()
        once.refresh_from_db()
        cleanup.refresh_from_db()

        due.enabled = False
        due.save()
        changed_names = sorted(scheduler.schedule)
        with app.connection_for_read() as connection:
            queue = connection.SimpleQueue("background_control")
            messages = []
            while queue.qsize():
                message = queue.get(block=False)
                messages.append(message.headers)
                message.ack()
        scheduler.close()
        lease.assert_owned()
        lease.close()
        print(json.dumps({
            "initial_names": initial_names,
            "changed_names": changed_names,
            "cron_timezone": cron_timezone,
            "due_count": due.total_run_count,
            "due_last_run": due_last_run,
            "once_count": once_count,
            "once_last_run": once_last_run,
            "once_disabled": not once.enabled,
            "cleanup_interval": cleanup.interval.every,
            "cleanup_crontab": cleanup.crontab_id,
            "cleanup_description": cleanup.description,
            "messages": messages,
            "lease_released": lease.connection.closed,
        }))
        """,
        tmp_path,
        database_url=postgres_test_database_url(),
    )
    assert observed["initial_names"] == [
        "celery.backend_cleanup",
        "due",
        "local-time",
        "once",
    ]
    assert "due" not in observed["changed_names"]
    assert "once" not in observed["changed_names"]
    assert observed["cron_timezone"] == "America/Cancun"
    assert observed["due_count"] == 1
    assert observed["due_last_run"]
    assert observed["once_count"] == 1
    assert observed["once_last_run"]
    assert observed["once_disabled"]
    assert observed["cleanup_interval"] == 86400  # noqa: PLR2004
    assert observed["cleanup_crontab"] is None
    assert observed["cleanup_description"] == "installer owns this schedule"
    assert len(observed["messages"]) == 2  # noqa: PLR2004
    assert all(not message["ignore_result"] for message in observed["messages"])
    assert observed["lease_released"]
