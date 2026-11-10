"""Web startup must not silently use AMQP for an empty Redis broker setting."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BASE_DIR: Path = Path(__file__).parents[3]
STARTUP_PROBE: str = """
import json

import config.wsgi
from celery import current_app

configuration = {
    "app": current_app.main,
    "eager": current_app.conf.task_always_eager,
    "store_eager_result": current_app.conf.task_store_eager_result,
}
if not current_app.conf.task_always_eager:
    # Construct the configured connection without contacting a broker.
    with current_app.connection_for_write() as connection:
        configuration.update({
        "transport": connection.transport.driver_type,
        "hostname": connection.hostname,
        })
print(json.dumps(configuration))
"""


def _web_startup(
    broker_url: str | None, *, eager: bool = False
) -> subprocess.CompletedProcess[str]:
    child_environment: dict[str, str] = os.environ.copy()
    child_environment.update(
        DJANGO_SETTINGS_MODULE="config.settings.local",
        DJANGO_READ_DOT_ENV_FILE="False",
        DJANGO_SECRET_KEY="celery-settings-probe-only",  # noqa: S106 - test-only key
        DJANGO_CELERY_USE_IMMEDIATE_BACKEND=str(eager),
    )
    if broker_url is None:
        child_environment.pop("CELERY_BROKER_URL", None)
    else:
        child_environment["CELERY_BROKER_URL"] = broker_url
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", STARTUP_PROBE],
        cwd=BASE_DIR,
        env=child_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


@pytest.mark.parametrize("broker_url", ["", " \t\n"])
def test_web_startup_rejects_blank_broker_url(broker_url: str) -> None:
    result: subprocess.CompletedProcess[str] = _web_startup(broker_url)
    assert result.returncode != 0
    assert "ImproperlyConfigured: CELERY_BROKER_URL must not be blank." in result.stderr


@pytest.mark.parametrize(
    ("broker_url", "hostname"),
    [
        (None, "localhost"),
        ("redis://configured-broker.invalid:6379/1", "configured-broker.invalid"),
    ],
)
def test_web_startup_uses_configured_or_default_redis(
    broker_url: str | None, hostname: str
) -> None:
    result: subprocess.CompletedProcess[str] = _web_startup(broker_url)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "app": "speleodb",
        "eager": False,
        "store_eager_result": False,
        "transport": "redis",
        "hostname": hostname,
    }


def test_stage_can_execute_immediately_without_a_broker() -> None:
    result: subprocess.CompletedProcess[str] = _web_startup("", eager=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "app": "speleodb",
        "eager": True,
        "store_eager_result": True,
    }
