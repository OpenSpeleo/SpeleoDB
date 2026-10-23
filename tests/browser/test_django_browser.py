"""Run browser UI/UX checks against pytest's real Django server."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import signal
import subprocess
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import pytest
from django.test import modify_settings
from django.test import override_settings
from django.urls import reverse

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISView
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectMutex
from speleodb.surveys.models import UserProjectPermission
from speleodb.testing.gitlab_pool import canonical_project
from speleodb.users.tests.factories import VerifiedUserFactory
from tests.browser.geographic_bound_fixtures import geographic_bound_records

if TYPE_CHECKING:
    from pytest_django.live_server_helper import LiveServer

    from speleodb.users.models import User

BASE_DIR: Path = Path(__file__).resolve().parents[2]


def controller_routes(user: User) -> dict[str, str]:
    """Materialize explicit form permissions without preparing any Git remote."""
    project: Project = canonical_project(PermissionLevel.ADMIN)
    UserProjectPermission.objects.create(
        project=project, target=user, level=PermissionLevel.ADMIN
    )
    ProjectMutex.objects.create(project=project, user=user)
    return {
        "project": reverse("private:project_details", kwargs={"project_id": project.id})
    }


@pytest.mark.django_db(transaction=True)
@override_settings(VITE_ALLOW_MISSING_MANIFEST=False)
def test_viewer_browser_workloads(
    request: pytest.FixtureRequest,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Keep browser timing separate from the serial backend suite and its load."""
    live_server: LiveServer = request.getfixturevalue("live_server")
    server_host: str | None = urlsplit(live_server.url).hostname
    assert server_host is not None
    manifest: Path = (
        BASE_DIR / "speleodb/common/static/speleodb/vite/.vite/manifest.json"
    )
    assert manifest.is_file()
    password: str = secrets.token_urlsafe(32)
    user: User = VerifiedUserFactory.create(
        email="viewer-browser@example.test",
        name="Viewer Browser",
        password=password,
    )
    public_view: GISView = GISView.objects.create(
        owner=user,
        name="Browser public view",
        allow_precise_zoom=False,
    )
    bun: str | None = shutil.which("bun")
    assert bun is not None, "Bun is required for browser workload checks"
    # Inherit the GitLab audit ledger. Credentials remain in the subprocess
    # environment, never its arguments or browser network trace artifacts.
    browser_environment: dict[str, str] = {
        **os.environ,
        "VIEWER_BROWSER_BASE_URL": live_server.url,
        "VIEWER_BROWSER_EMAIL": user.email,
        "VIEWER_BROWSER_PASSWORD": password,
        "VIEWER_BROWSER_PUBLIC_URL": reverse(
            "gis_view_map", kwargs={"gis_token": public_view.gis_token}
        ),
        "VIEWER_BROWSER_ROUTES": json.dumps(controller_routes(user)),
    }
    command: list[str] = [bun, "run", "test:browser"]
    browser_grep: str | None = os.environ.get("VIEWER_BROWSER_GREP")
    if browser_grep:
        command.extend(["--grep", browser_grep])
    process: subprocess.Popen[str]
    # Keep Playwright's per-case progress visible while this single pytest test
    # orchestrates the whole serial browser suite.
    with (
        # Dynamic fixture lookup retains its normal lifecycle, but its autouse
        # host helper runs earlier; configure the chosen host through Django.
        modify_settings(ALLOWED_HOSTS={"append": server_host}),
        geographic_bound_records() as bound_records,
        capfd.disabled(),
        subprocess.Popen(  # noqa: S603 - fixed root script
            command,
            cwd=BASE_DIR,
            env={
                **browser_environment,
                "VIEWER_BROWSER_BOUND_RECORDS": json.dumps(bound_records),
            },
            text=True,
            start_new_session=True,
        ) as process,
    ):
        try:
            process.wait(timeout=1800)
        finally:
            if process.poll() is None:
                # Bun, Playwright and its browser workers share this new group.
                # A timeout/interruption must not leave renderer workers alive.
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    assert process.returncode == 0, (
        f"Playwright exited with status {process.returncode}; "
        "see the browser output above and report.json in the browser artifacts"
    )
