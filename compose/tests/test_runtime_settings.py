"""Subprocess coverage of scheduler isolation and application worker profiles."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPOSITORY_ROOT: Path = Path(__file__).resolve().parents[2]
SETTINGS_PROBE: str = """
import json
import sys
from pathlib import Path

import django
from django.conf import settings

django.setup()
from config.celery_app import app

app.loader.import_default_modules()
database = settings.DATABASES['default']
print(json.dumps({
    'apps': settings.INSTALLED_APPS,
    'modules': list(sys.modules),
    'database': {key: database.get(key) for key in (
        'ENGINE', 'HOST', 'PORT', 'NAME', 'OPTIONS', 'CONN_MAX_AGE'
    )},
    'timezone': settings.TIME_ZONE,
    'celery_timezone': app.conf.timezone,
    'broker': app.conf.broker_url,
    'routes': app.conf.task_routes,
    'serializer': app.conf.task_serializer,
    'result_backend': app.conf.result_backend,
    'result_expires': app.conf.result_expires,
    'task_events': app.conf.worker_send_task_events,
    'sent_events': app.conf.task_send_sent_event,
    'tasks': list(app.tasks),
    'threads': len(list(Path('/proc/self/task').iterdir())),
}))
"""


def settings_snapshot(
    settings_module: str, overrides: dict[str, str]
) -> dict[str, Any]:
    environment: dict[str, str] = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": settings_module,
            "DJANGO_READ_DOT_ENV_FILE": "false",
            "DJANGO_SECRET_KEY": "runtime-settings-tests-only",
            "CELERY_SKIP_CHECKS": "true",
            **overrides,
        }
    )
    result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        [sys.executable, "-c", SETTINGS_PROBE],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    snapshot: dict[str, Any] = json.loads(result.stdout)
    return snapshot


def test_beat_loads_only_schedule_models_and_no_application_tasks() -> None:
    snapshot: dict[str, Any] = settings_snapshot(
        "config.settings.beat",
        {
            "USE_DOCKER": "false",
            "DATABASE_URL": "postgres://scheduler@db.invalid/schedules",
            "CELERY_BROKER_URL": "memory://",
        },
    )
    assert snapshot["apps"] == ["django_celery_beat"]
    assert snapshot["threads"] == 1
    assert snapshot["result_backend"] is None
    assert snapshot["result_expires"] is None
    assert snapshot["task_events"] is False
    assert snapshot["sent_events"] is False
    assert snapshot["timezone"] == snapshot["celery_timezone"] == "America/New_York"
    assert snapshot["broker"] == "memory://"
    assert snapshot["serializer"] == "json"
    assert snapshot["routes"]["speleodb.background_jobs.tasks.generate_export"] == {
        "queue": "exports"
    }
    assert not any(task.startswith("speleodb.") for task in snapshot["tasks"])
    forbidden: tuple[str, ...] = (
        "config.settings.base",
        "config.settings.local",
        "config.settings.production",
        "speleodb.surveys",
        "speleodb.users",
        "speleodb.background_jobs.tasks",
        "django_celery_results",
        "django.contrib.admin",
        "sentry_sdk",
        "numpy",
        "pandas",
        "matplotlib",
        "scipy",
        "PIL",
        "moviepy",
    )
    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in snapshot["modules"]
        for prefix in forbidden
    )


def test_beat_preserves_database_url_options_and_connection_lifetime() -> None:
    snapshot: dict[str, Any] = settings_snapshot(
        "config.settings.beat",
        {
            "USE_DOCKER": "false",
            "DATABASE_URL": (
                "postgres://scheduler@db.invalid:5543/schedules"
                "?sslmode=require&connect_timeout=7"
            ),
            "CONN_MAX_AGE": "23",
        },
    )
    assert snapshot["database"] == {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "db.invalid",
        "PORT": 5543,
        "NAME": "schedules",
        "OPTIONS": {"sslmode": "require", "connect_timeout": 7},
        "CONN_MAX_AGE": 23,
    }


def test_beat_uses_the_compose_postgres_connection_contract() -> None:
    snapshot: dict[str, Any] = settings_snapshot(
        "config.settings.beat",
        {
            "USE_DOCKER": "true",
            "POSTGRES_HOST": "compose-db.invalid",
            "POSTGRES_PORT": "5544",
            "POSTGRES_DB": "compose-schedules",
            "POSTGRES_USER": "scheduler",
            "POSTGRES_PASSWORD": "runtime-settings-tests-only",
            "CONN_MAX_AGE": "0",
        },
    )
    assert snapshot["database"] == {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "compose-db.invalid",
        "PORT": "5544",
        "NAME": "compose-schedules",
        "OPTIONS": {},
        "CONN_MAX_AGE": 0,
    }


@pytest.mark.parametrize("worker_runtime", ["true", "false"])
def test_worker_profile_preserves_tasks_and_results_without_admin_autodiscovery(
    worker_runtime: str,
) -> None:
    snapshot: dict[str, Any] = settings_snapshot(
        "config.settings.local", {"SPELEODB_CELERY_WORKER_RUNTIME": worker_runtime}
    )
    assert snapshot["result_backend"] == "django-db"
    assert snapshot["result_expires"] == 30 * 24 * 60 * 60
    assert snapshot["task_events"] is False
    assert snapshot["sent_events"] is False
    expected_tasks: set[str] = {
        "speleodb.background_jobs.tasks.generate_export",
        "speleodb.background_jobs.tasks.maintain_background_jobs",
        "speleodb.surveys.tasks.refresh_all_projects_geojson",
        "speleodb.users.tasks.get_users_count",
        "celery.backend_cleanup",
    }
    assert expected_tasks <= set(snapshot["tasks"])
    if worker_runtime == "true":
        assert "django.contrib.admin.apps.SimpleAdminConfig" in snapshot["apps"]
        assert not {"debug_toolbar", "silk", "django_extensions", "hijack"} & set(
            snapshot["apps"]
        )
        assert "speleodb.background_jobs.admin" not in snapshot["modules"]
        assert "config.urls" not in snapshot["modules"]
    else:
        assert "django.contrib.admin" in snapshot["apps"]
        assert {"debug_toolbar", "silk", "django_extensions"} <= set(snapshot["apps"])
        assert "speleodb.background_jobs.admin" in snapshot["modules"]
