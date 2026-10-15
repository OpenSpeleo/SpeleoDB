from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).parents[3]


def test_test_settings_accept_devcontainer_internal_service_endpoints() -> None:
    child_environment = os.environ.copy()
    child_environment.update(
        {
            "AWS_S3_TEST_ENDPOINT_URL": "http://rustfs:9000",
            "DJANGO_SETTINGS_MODULE": "config.settings.test",
            "GITLAB_TEST_HOST_URL": "gitlab:9080",
        }
    )
    probe = """
import json
import django
from django.conf import settings

django.setup()
print(json.dumps({
    "gitlab_host": settings.GITLAB_HOST_URL,
    "gitlab_protocol": settings.GITLAB_HTTP_PROTOCOL,
    "s3_endpoint": settings.AWS_S3_ENDPOINT_URL,
    "atomic_requests": settings.DATABASES["default"]["ATOMIC_REQUESTS"],
}))
"""

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", probe],
        cwd=BASE_DIR,
        env=child_environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == {
        "gitlab_host": "gitlab:9080",
        "gitlab_protocol": "http",
        "s3_endpoint": "http://rustfs:9000",
        "atomic_requests": True,
    }


@pytest.mark.parametrize(
    ("database_url", "engine", "template"),
    [
        (
            "postgresql://test@db.invalid/runtime-settings-test",
            "django.db.backends.postgresql",
            "template0",
        ),
        ("sqlite://:memory:", "django.db.backends.sqlite3", None),
    ],
)
def test_test_database_template_is_isolated_only_for_postgresql(
    database_url: str, engine: str, template: str | None
) -> None:
    child_environment: dict[str, str] = os.environ.copy()
    child_environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.test",
            "TEST_DATABASE_URL": database_url,
        }
    )
    probe: str = """
import json
from django.conf import settings

database = settings.DATABASES["default"]
print(json.dumps({
    "engine": database["ENGINE"],
    "template": database.get("TEST", {}).get("TEMPLATE"),
    "atomic_requests": database["ATOMIC_REQUESTS"],
}))
"""
    result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        [sys.executable, "-c", probe],
        cwd=BASE_DIR,
        env=child_environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert json.loads(result.stdout) == {
        "engine": engine,
        "template": template,
        "atomic_requests": True,
    }
