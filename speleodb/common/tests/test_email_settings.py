from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

BASE_DIR: Path = Path(__file__).parents[3]


@pytest.mark.parametrize(
    ("settings_module", "backend"),
    [
        ("config.settings.base", None),
        ("config.settings.local", None),
        ("config.settings.local", "django.core.mail.backends.smtp.EmailBackend"),
        ("config.settings.local", "django.core.mail.backends.filebased.EmailBackend"),
        ("config.settings.local", "django.core.mail.backends.locmem.EmailBackend"),
        ("config.settings.local", "django.core.mail.backends.dummy.EmailBackend"),
        ("config.settings.test", None),
    ],
)
def test_mailer_settings_construct_working_backends(
    settings_module: str, backend: str | None, tmp_path: Path
) -> None:
    child_environment: dict[str, str] = os.environ.copy()
    child_environment.update(
        DJANGO_SETTINGS_MODULE=settings_module,
        DJANGO_READ_DOT_ENV_FILE="False",
    )
    child_environment.pop("DJANGO_EMAIL_BACKEND", None)
    if backend is not None:
        child_environment["DJANGO_EMAIL_BACKEND"] = backend
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
    assert (mailer.host, mailer.port, mailer.timeout) == ("localhost", 25, 5)
else:
    assert mailer.send_messages([
        EmailMessage(
            "Mailer probe", "Delivery body", "from@example.com", ["to@example.com"]
        )
    ]) == 1
    if hasattr(mailer, "file_path"):
        files = list(Path(mailer.file_path).iterdir())
        assert len(files) == 1
        assert "Delivery body" in files[0].read_text()
        if type(mailer).__name__ == "EmailEMLBackend":
            assert files[0].suffix == ".eml"
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
