from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

BASE_DIR: Path = Path(__file__).parents[3]


@pytest.mark.parametrize(
    ("settings_module", "backend", "smtp_override"),
    [
        ("config.settings.base", None, False),
        ("config.settings.local", None, False),
        ("config.settings.local", None, True),
        ("config.settings.local", "django.core.mail.backends.smtp.EmailBackend", False),
        (
            "config.settings.local",
            "django.core.mail.backends.locmem.EmailBackend",
            True,
        ),
        (
            "config.settings.local",
            "django.core.mail.backends.dummy.EmailBackend",
            False,
        ),
        ("config.settings.test", None, False),
    ],
)
def test_mailer_settings_construct_working_backends(
    settings_module: str, backend: str | None, smtp_override: bool, tmp_path: Path
) -> None:
    child_environment: dict[str, str] = os.environ.copy()
    child_environment.update(
        DJANGO_SETTINGS_MODULE=settings_module,
        DJANGO_READ_DOT_ENV_FILE="False",
        # Local settings require an environment key; test settings' default
        # does not populate os.environ for this subprocess.
        DJANGO_SECRET_KEY="mailer-settings-probe-only",  # noqa: S106 - test-only key
    )
    for key in ("DJANGO_EMAIL_BACKEND", "DJANGO_EMAIL_HOST", "DJANGO_EMAIL_PORT"):
        child_environment.pop(key, None)
    if backend is not None:
        child_environment["DJANGO_EMAIL_BACKEND"] = backend
    if smtp_override:
        child_environment.update(DJANGO_EMAIL_HOST="mailpit", DJANGO_EMAIL_PORT="2525")
    probe: str = """
import os
import sys
import warnings
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage, mailers
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend
from django.utils.deprecation import RemovedInDjango70Warning

warnings.simplefilter("error", RemovedInDjango70Warning)
assert settings.MAILERS
os.chdir(sys.argv[1])
mailer = mailers.default
if isinstance(mailer, SMTPBackend):
    expected_port = 1025 if settings.SETTINGS_MODULE.endswith("local") else 25
    expected_host = os.environ.get("DJANGO_EMAIL_HOST", "localhost")
    expected_port = int(os.environ.get("DJANGO_EMAIL_PORT", expected_port))
    assert (mailer.host, mailer.port, mailer.timeout) == (
        expected_host, expected_port, 5
    )
else:
    assert mailer.send_messages([
        EmailMessage(
            "Mailer probe", "Delivery body", "from@example.com", ["to@example.com"]
        )
    ]) == 1
"""
    result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        [sys.executable, "-c", probe, str(tmp_path)],
        cwd=BASE_DIR,
        env=child_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
