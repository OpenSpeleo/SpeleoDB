"""Protect the shared infrastructure and real container startup contracts."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import pytest
import yaml
from celery import Celery
from celery._state import get_current_app
from django.db import connection
from redis import Redis

from compose.setup_local_gitlab import read_env_file
from config.celery_app import app
from speleodb.testing.celery import isolated_test_broker_url
from speleodb.testing.database import postgres_test_database_url

if TYPE_CHECKING:
    from collections.abc import Iterator

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKGROUND_SERVICES = ("celery-worker", "celery-beat")
WORKER_START_TIMEOUT_SECONDS: int = 60
NATIVE_THREAD_VARIABLES: tuple[str, ...] = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
)


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
    assert services["celery-worker"]["container_name"] == (
        "${COMPOSE_INSTANCE_PREFIX:-speleodb}_local_celery_worker"
    )
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


@pytest.fixture
def worker_script_environment(transactional_db: None) -> dict[str, str]:
    if connection.vendor != "postgresql":
        pytest.skip("Real worker startup requires the isolated PostgreSQL test DB.")
    environment: dict[str, str] = os.environ.copy()
    for name in NATIVE_THREAD_VARIABLES:
        environment.pop(name, None)
    broker_url: str = isolated_test_broker_url()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "compose.tests.worker_settings",
            "TEST_DATABASE_URL": postgres_test_database_url(),
            "CELERY_BROKER_URL": broker_url,
            "TEST_CELERY_BROKER_URL": broker_url,
            "SPELEODB_TEST_BROKER_PREFIX": f"worker-start-{uuid.uuid4()}:",
            "PYTHONUNBUFFERED": "1",
        }
    )
    return environment


@contextmanager
def running_script_worker(
    environment: dict[str, str], tmp_path: Path
) -> Iterator[tuple[subprocess.Popen[bytes], Celery, str]]:
    previous_app: Celery = get_current_app()
    broker_url: str = environment["TEST_CELERY_BROKER_URL"]
    key_prefix: str = environment["SPELEODB_TEST_BROKER_PREFIX"]
    log_path: Path = tmp_path / f"worker-{uuid.uuid4()}.log"
    with Celery("worker-script-tests", broker=broker_url) as application:
        application.conf.update(
            broker_read_url=broker_url,
            broker_write_url=broker_url,
            broker_transport_options={"global_keyprefix": key_prefix},
        )
        with log_path.open("wb") as log:
            process: subprocess.Popen[bytes] = subprocess.Popen(  # noqa: S603
                ["/bin/bash", str(REPOSITORY_ROOT / "compose/celery/worker/start")],
                cwd=REPOSITORY_ROOT,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        try:
            deadline: float = time.monotonic() + WORKER_START_TIMEOUT_SECONDS
            hostname: str | None = None
            while time.monotonic() < deadline:
                assert process.poll() is None, log_path.read_text()
                replies: dict[str, Any] | None = application.control.inspect(
                    timeout=1
                ).stats()
                if replies:
                    matches: list[str] = [
                        name
                        for name, stats in replies.items()
                        if stats["pid"] == process.pid
                    ]
                    if matches:
                        [hostname] = matches
                        break
                time.sleep(0.2)
            assert hostname is not None, log_path.read_text()
            yield process, application, hostname
        finally:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            previous_app.set_current()
            # Delete only this test's unique namespace on the dedicated broker.
            with Redis.from_url(broker_url) as broker:
                for key in broker.scan_iter(match=f"{key_prefix}*"):
                    broker.delete(key)


@pytest.mark.skipif(
    os.environ.get("EXPORTS_LIVE_WORKER_TESTS") != "1",
    reason="Set EXPORTS_LIVE_WORKER_TESTS=1 to use the isolated real broker.",
)
@pytest.mark.parametrize("explicit_threads", [None, "3"])
def test_worker_script_runs_both_queues_with_unique_names_and_native_thread_limits(
    tmp_path: Path,
    worker_script_environment: dict[str, str],
    explicit_threads: str | None,
) -> None:
    environment: dict[str, str] = worker_script_environment
    if explicit_threads is not None:
        environment.update(dict.fromkeys(NATIVE_THREAD_VARIABLES, explicit_threads))
    names: set[str] = set()
    for _ in range(2):
        with running_script_worker(environment, tmp_path) as (
            process,
            application,
            hostname,
        ):
            assert hostname not in names
            names.add(hostname)
            assert hostname.startswith("worker-")
            uuid.UUID(hostname.split("@", maxsplit=1)[0].removeprefix("worker-"))
            inspector = application.control.inspect(destination=[hostname], timeout=3)
            queues: dict[str, Any] | None = inspector.active_queues()
            assert queues is not None
            assert {queue["name"] for queue in queues[hostname]} == {
                "exports",
                "background_control",
            }
            statistics: dict[str, Any] | None = inspector.stats()
            assert statistics is not None
            assert statistics[hostname]["pool"]["max-concurrency"] == 1
            assert statistics[hostname]["pool"]["implementation"].endswith(
                ".prefork:TaskPool"
            )
            assert statistics[hostname]["prefetch_count"] == 1
            command: list[str] = (
                Path(f"/proc/{process.pid}/cmdline").read_text().split("\0")
            )
            assert "--events" in command
            assert "--skip-checks" in command
            process_environment: dict[str, str] = dict(
                entry.split("=", maxsplit=1)
                for entry in Path(f"/proc/{process.pid}/environ")
                .read_text()
                .split("\0")
                if entry
            )
            assert process_environment["SPELEODB_CELERY_WORKER_RUNTIME"] == "true"
            for name in NATIVE_THREAD_VARIABLES:
                assert process_environment[name] == (explicit_threads or "1")


@pytest.mark.skipif(
    os.environ.get("EXPORTS_LIVE_WORKER_TESTS") != "1",
    reason="Set EXPORTS_LIVE_WORKER_TESTS=1 to use the isolated real broker.",
)
def test_worker_script_does_not_start_after_real_django_check_failure(
    worker_script_environment: dict[str, str],
) -> None:
    environment: dict[str, str] = worker_script_environment
    environment["SPELEODB_TEST_INVALID_STATIC_URL"] = "1"
    result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        ["/bin/bash", str(REPOSITORY_ROOT / "compose/celery/worker/start")],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=WORKER_START_TIMEOUT_SECONDS,
    )
    assert result.returncode == 1
    assert "SystemCheckError" in result.stderr
    assert "urls.E006" in result.stderr
    assert "ready." not in result.stdout
    assert "ready." not in result.stderr


@pytest.mark.django_db(transaction=True)
def test_entrypoint_checks_real_postgres_and_preserves_broker() -> None:
    if connection.vendor != "postgresql":
        pytest.skip("The real entrypoint readiness check requires PostgreSQL.")
    postgres_test_database_url()
    database: dict[str, Any] = connection.settings_dict
    environment: dict[str, str] = os.environ.copy()
    environment.update(
        {
            "POSTGRES_USER": str(database["USER"]),
            "POSTGRES_PASSWORD": str(database["PASSWORD"]),
            "POSTGRES_HOST": str(database["HOST"]),
            "POSTGRES_PORT": str(database["PORT"]),
            "POSTGRES_DB": str(database["NAME"]),
            "REDIS_URL": "redis://cache:6379/0",
            "CELERY_BROKER_URL": "redis://isolated-test-broker:6381/0",
        }
    )
    result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        [
            "/bin/bash",
            str(REPOSITORY_ROOT / "compose/entrypoint"),
            sys.executable,
            "-c",
            "import os; print(os.environ['CELERY_BROKER_URL'])",
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    assert result.stdout.strip() == "redis://isolated-test-broker:6381/0"
    assert "PostgreSQL is available" in result.stderr


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


def test_setup_shell_orders_migrations_before_schedules_and_superuser() -> None:
    setup_path: Path = REPOSITORY_ROOT / "compose/setup"
    setup: str = setup_path.read_text(encoding="utf-8")
    subprocess.run(["/bin/bash", "-n", str(setup_path)], check=True)  # noqa: S603
    commands: list[str] = setup.splitlines()
    assert commands.index("set -o errexit") < commands.index("python manage.py migrate")
    assert commands.index("python manage.py migrate") < commands.index(
        "python manage.py install_background_schedules"
    )
    assert commands.index(
        "python manage.py install_background_schedules"
    ) < commands.index("python manage.py ensure_local_superuser")
