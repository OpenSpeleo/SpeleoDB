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
from django.conf import settings

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
    ("database_url", "expected_name", "use_template"),
    [
        (None, "configured-tests", False),
        ("postgresql://test@db.invalid/test_worker", "test_worker", False),
        ("sqlite://:memory:", None, False),
        (None, "development", True),
    ],
)
def test_test_database_selection_is_explicit_and_postgresql(
    database_url: str | None,
    expected_name: str | None,
    use_template: bool,
    tmp_path: Path,
) -> None:
    test_environment = tmp_path / ".envs" / "test.env"
    test_environment.parent.mkdir()
    test_environment.write_text(
        (BASE_DIR / ".envs/test.env.dist").read_text()
        if use_template
        else "DATABASE_URL=postgresql://test@db.invalid/configured-tests\n"
    )
    child_environment: dict[str, str] = os.environ.copy()
    child_environment.pop("TEST_DATABASE_URL", None)
    child_environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.test",
            "USE_DOCKER": "true",
            "POSTGRES_HOST": "development-db.invalid",
            "POSTGRES_DB": "development",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": "unused",
            "POSTGRES_PASSWORD": "unused",
        }
    )
    if database_url is not None:
        child_environment["TEST_DATABASE_URL"] = database_url
    probe: str = """
import json
from django.conf import settings

database = settings.DATABASES["default"]
print(json.dumps({
    "engine": database["ENGINE"],
    "name": database["NAME"],
    "host": database["HOST"],
    "template": database.get("TEST", {}).get("TEMPLATE"),
    "atomic_requests": database["ATOMIC_REQUESTS"],
}))
"""
    result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        env=child_environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if expected_name is None:
        assert result.returncode != 0
        assert "The complete backend suite requires PostgreSQL" in result.stderr
        return
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "engine": "django.db.backends.postgresql",
        "name": expected_name,
        "host": "development-db.invalid" if use_template else "db.invalid",
        "template": "template0",
        "atomic_requests": True,
    }
