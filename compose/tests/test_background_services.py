"""Protect the shared infrastructure and real container startup contracts."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest
import yaml

from compose.setup_local_gitlab import read_env_file
from config.celery_app import app

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKGROUND_SERVICES = ("celery-worker", "celery-beat")
MIGRATION_FAILURE_EXIT_CODE = 23


@pytest.mark.parametrize(
    ("task_name", "queue_name"),
    [
        ("speleodb.background_jobs.tasks.generate_export", "exports"),
        (
            "speleodb.background_jobs.tasks.maintain_background_jobs",
            "background_control",
        ),
        ("speleodb.surveys.tasks.refresh_all_projects_geojson", "background_control"),
        ("speleodb.surveys.tasks.refresh_project_geojson", "background_control"),
        ("speleodb.users.tasks.get_users_count", "background_control"),
        ("celery.backend_cleanup", "background_control"),
    ],
)
def test_existing_and_export_tasks_route_to_queues_the_worker_consumes(
    task_name: str, queue_name: str
) -> None:
    route: dict[str, Any] = app.amqp.router.route({}, task_name)
    assert route["queue"].name == queue_name


@pytest.fixture
def compose_config() -> dict[str, Any]:
    configuration: object = yaml.safe_load(
        (REPOSITORY_ROOT / "local.yml").read_text(encoding="utf-8")
    )
    assert isinstance(configuration, dict)
    return configuration


@pytest.mark.parametrize(
    "service_name",
    ["django", "django-webserver", "celery-worker", "celery-beat", "setup", "gitlab"],
)
def test_existing_gitlab_namespace_reaches_every_application_and_setup_service(
    compose_config: dict[str, Any], service_name: str
) -> None:
    # The root .env may name a populated legacy namespace. A tracked default in
    # an env_file must not redirect either the worker or bootstrap to a new group.
    assert (
        compose_config["services"][service_name]["environment"]["GITLAB_GROUP_NAME"]
        == "${GITLAB_GROUP_NAME:-speleodb}"
    )
    assert "GITLAB_GROUP_NAME" not in read_env_file(REPOSITORY_ROOT / ".envs/.django")


def test_background_services_start_after_migrations_without_kanchi(
    compose_config: dict[str, Any],
) -> None:
    services: dict[str, Any] = compose_config["services"]
    for name in BACKGROUND_SERVICES:
        service: dict[str, Any] = services[name]
        assert service["depends_on"] == {
            "setup": {"condition": "service_completed_successfully"},
            "redis": {"condition": "service_healthy"},
        }
        assert "profiles" not in service
        assert service["stop_grace_period"] == "120s"
        assert service["user"] == "dev-user"
        assert service["environment"]["CELERY_BROKER_URL"] == (
            "${CELERY_BROKER_URL:-redis://localhost:6379/1}"
        )
    assert services["celery-worker"].get("container_name") is None
    assert "celery-exports" not in services
    assert "celery-maintenance" not in services


def test_shared_redis_is_durable_with_separate_broker_database(
    compose_config: dict[str, Any],
) -> None:
    services: dict[str, Any] = compose_config["services"]
    broker: dict[str, Any] = services["redis"]
    assert "celery-redis" not in services
    assert broker["ports"] == ["127.0.0.1:6379:6379"]
    assert broker["command"] == [
        "redis-server",
        "--appendonly",
        "yes",
        "--maxmemory-policy",
        "noeviction",
    ]
    assert broker["volumes"] == ["speleodb_local_redis_data:/data"]


def test_kanchi_uses_shared_postgres_with_its_own_database_credentials(
    compose_config: dict[str, Any],
) -> None:
    services: dict[str, Any] = compose_config["services"]
    kanchi: dict[str, Any] = services["kanchi"]
    assert kanchi["depends_on"] == {
        "redis": {"condition": "service_healthy"},
        "postgres": {"condition": "service_healthy"},
        "setup": {"condition": "service_completed_successfully"},
    }
    assert "env_file" not in kanchi
    assert "volumes" not in kanchi
    assert "entrypoint" not in kanchi
    assert "network_mode" not in kanchi
    assert kanchi["ports"] == ["127.0.0.1:8765:8765"]
    environment: dict[str, str] = kanchi["environment"]
    assert environment["AUTH_ENABLED"] == "true"
    assert environment["AUTH_BASIC_ENABLED"] == "true"
    assert environment["ENABLE_PICKLE_SERIALIZATION"] == "false"
    assert environment["DATABASE_URL"].startswith("postgresql+psycopg://")
    assert "@postgres:5432/kanchi" in environment["DATABASE_URL"]
    assert environment["CELERY_BROKER_URL"] == (
        "${KANCHI_CELERY_BROKER_URL:-redis://redis:6379/1}"
    )
    assert not any(
        key.startswith(("AWS_", "GITLAB_", "MAILERSEND_", "DJANGO_"))
        for key in environment
    )
    assert "kanchi-postgres" not in services
    assert services["setup"]["environment"]["KANCHI_POSTGRES_PASSWORD"] == (
        "${KANCHI_POSTGRES_PASSWORD:-kanchi-local-only}"  # noqa: S105 - Local default.
    )


def test_live_tests_have_separate_pubsub_broker(
    compose_config: dict[str, Any],
) -> None:
    broker: dict[str, Any] = compose_config["services"]["celery-test-redis"]
    assert broker["profiles"] == ["integration-test"]
    assert broker["ports"] == ["127.0.0.1:6381:6379"]
    assert "volumes" not in broker


def test_worker_script_consumes_both_queues_with_unique_replica_names(
    tmp_path: Path,
) -> None:
    executable: Path = tmp_path / "celery"
    executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n', encoding="utf-8")
    executable.chmod(0o700)
    environment: dict[str, str] = os.environ.copy()
    environment["PATH"] = f"{tmp_path}:{environment['PATH']}"
    names: set[str] = set()
    expected_arguments: list[str] = [
        "-A",
        "config.celery_app",
        "worker",
        "--loglevel",
        "INFO",
        "--events",
        "--queues",
        "exports,background_control",
        "--concurrency",
        "1",
        "--prefetch-multiplier",
        "1",
        "--hostname",
    ]
    for _ in range(2):
        result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
            ["/bin/bash", str(REPOSITORY_ROOT / "compose/celery/worker/start")],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        arguments: list[str] = result.stdout.splitlines()
        assert arguments[:-1] == expected_arguments
        hostname: str = arguments[-1]
        assert hostname.startswith("worker-")
        assert hostname.endswith("@%h")
        uuid.UUID(hostname.removeprefix("worker-").removesuffix("@%h"))
        assert hostname not in names
        names.add(hostname)


def test_entrypoint_preserves_explicit_broker(tmp_path: Path) -> None:
    executable: Path = tmp_path / "python"
    executable.write_text("#!/bin/sh\ncat >/dev/null\n", encoding="utf-8")
    executable.chmod(0o700)
    environment: dict[str, str] = os.environ.copy()
    environment.update(
        {
            "PATH": f"{tmp_path}:{environment['PATH']}",
            "POSTGRES_USER": "test",
            "POSTGRES_PASSWORD": "local-test-only",
            "POSTGRES_HOST": "localhost",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DB": "test",
            "REDIS_URL": "redis://cache:6379/0",
            "CELERY_BROKER_URL": "redis://isolated-test-broker:6379/0",
        }
    )
    result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        [
            "/bin/bash",
            str(REPOSITORY_ROOT / "compose/entrypoint"),
            "/bin/sh",
            "-c",
            'printf "%s" "$CELERY_BROKER_URL"',
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.stdout == "redis://isolated-test-broker:6379/0"


def test_test_settings_override_the_inherited_development_broker() -> None:
    environment: dict[str, str] = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.test",
            "CELERY_BROKER_URL": "redis://localhost:6379/1",
            "TEST_CELERY_BROKER_URL": "memory://",
        }
    )
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            "-c",
            "import django; django.setup(); "
            "from config.celery_app import app; "
            "print(app.conf.broker_url); "
            "print(app.connection_for_write().as_uri())",
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    configured_broker, connection_uri = result.stdout.strip().splitlines()
    assert configured_broker == "memory://"
    assert connection_uri.startswith("memory://")


def test_setup_stops_on_migration_failure(tmp_path: Path) -> None:
    log: Path = tmp_path / "commands"
    executable: Path = tmp_path / "python"
    executable.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" >> "$COMMAND_LOG"\n'
        'if [ "$*" = "manage.py migrate" ]; then exit 23; fi\n',
        encoding="utf-8",
    )
    executable.chmod(0o700)
    # Skip the root-only ownership branch without requiring a privileged test.
    identity: Path = tmp_path / "id"
    identity.write_text("#!/bin/sh\nprintf '1000\\n'\n", encoding="utf-8")
    identity.chmod(0o700)
    setup: str = (REPOSITORY_ROOT / "compose/setup").read_text(encoding="utf-8")
    setup = setup.replace("bash /app/compose/prepare_node_modules", ":")
    environment: dict[str, str] = os.environ.copy()
    environment.update(
        {"PATH": f"{tmp_path}:{environment['PATH']}", "COMMAND_LOG": str(log)}
    )
    result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        ["/bin/bash", "-c", setup],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == MIGRATION_FAILURE_EXIT_CODE
    commands: str = log.read_text(encoding="utf-8")
    assert "manage.py migrate" in commands
    assert "install_background_schedules" not in commands
    assert "ensure_local_superuser" not in commands
