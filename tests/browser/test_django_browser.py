"""Run the unchanged browser workloads against pytest's real Django server."""

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

import pytest
from allauth.account.models import EmailAddress
from django.test import override_settings
from django.urls import resolve
from django.urls import reverse

from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import SurveyTeamMembershipRole
from speleodb.gis.models import CylinderFleet
from speleodb.gis.models import CylinderFleetUserPermission
from speleodb.gis.models import Experiment
from speleodb.gis.models import ExperimentUserPermission
from speleodb.gis.models import GISView
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import LandmarkCollectionUserPermission
from speleodb.gis.models import SensorFleet
from speleodb.gis.models import SensorFleetUserPermission
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectMutex
from speleodb.surveys.models import UserProjectPermission
from speleodb.testing.gitlab_pool import canonical_project
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from tests.browser.urls import revision_fixture
from tests.browser.urls import tree_fixture

if TYPE_CHECKING:
    from pytest_django.live_server_helper import LiveServer

    from speleodb.users.models import User

BASE_DIR: Path = Path(__file__).resolve().parents[2]


def controller_routes(user: User) -> dict[str, str]:
    """Materialize explicit form permissions without preparing any Git remote."""
    project: Project = canonical_project(PermissionLevel.ADMIN)
    readonly: Project = canonical_project(PermissionLevel.READ_ONLY)
    UserProjectPermission.objects.create(
        project=project, target=user, level=PermissionLevel.ADMIN
    )
    UserProjectPermission.objects.create(
        project=readonly, target=user, level=PermissionLevel.READ_ONLY
    )
    ProjectMutex.objects.create(project=project, user=user)
    team: SurveyTeam = SurveyTeam.objects.create(
        name="Browser permission team", description="Browser fixture", country="MX"
    )
    SurveyTeamMembership.objects.create(
        team=team, user=user, role=SurveyTeamMembershipRole.LEADER
    )
    routes: dict[str, str] = {
        "project": reverse(
            "private:project_details", kwargs={"project_id": project.id}
        ),
        "readonly_project": reverse(
            "private:project_details", kwargs={"project_id": readonly.id}
        ),
    }
    cylinder: CylinderFleet = CylinderFleet.objects.create(
        name="Browser cylinders", created_by=user.email
    )
    CylinderFleetUserPermission.objects.create(
        cylinder_fleet=cylinder, user=user, level=PermissionLevel.ADMIN
    )
    routes["cylinder"] = reverse(
        "private:cylinder_fleet_details", kwargs={"fleet_id": cylinder.id}
    )
    sensor: SensorFleet = SensorFleet.objects.create(
        name="Browser sensors", created_by=user.email
    )
    SensorFleetUserPermission.objects.create(
        sensor_fleet=sensor, user=user, level=PermissionLevel.ADMIN
    )
    routes["sensor"] = reverse(
        "private:sensor_fleet_details", kwargs={"fleet_id": sensor.id}
    )
    readonly_fleet: CylinderFleet = CylinderFleet.objects.create(
        name="Read-only browser cylinders", created_by=user.email
    )
    CylinderFleetUserPermission.objects.create(
        cylinder_fleet=readonly_fleet, user=user, level=PermissionLevel.READ_ONLY
    )
    routes["readonly_cylinder"] = reverse(
        "private:cylinder_fleet_details", kwargs={"fleet_id": readonly_fleet.id}
    )
    experiment: Experiment = Experiment.objects.create(
        name="Browser experiment", created_by=user.email
    )
    ExperimentUserPermission.objects.create(
        experiment=experiment, user=user, level=PermissionLevel.READ_ONLY
    )
    routes["experiment"] = reverse(
        "private:experiment_data_viewer", kwargs={"experiment_id": experiment.id}
    )
    collection: LandmarkCollection = LandmarkCollection.objects.create(
        name="Browser landmarks", created_by=user.email
    )
    LandmarkCollectionUserPermission.objects.create(
        collection=collection, user=user, level=PermissionLevel.READ_ONLY
    )
    routes["landmarks"] = reverse(
        "private:landmark_collection_details", kwargs={"collection_id": collection.id}
    )
    # Fail before browser launch if either synchronous request could reach Git.
    assert (
        resolve(reverse("api:v2:project-revisions", kwargs={"id": project.id})).func
        is revision_fixture
    )
    assert (
        resolve(
            reverse(
                "api:v2:project-gitexplorer",
                kwargs={"id": project.id, "hexsha": "a" * 40},
            )
        ).func
        is tree_fixture
    )
    return routes


@pytest.mark.django_db(transaction=True)
@override_settings(
    VITE_ALLOW_MISSING_MANIFEST=False,
    ROOT_URLCONF="tests.browser.urls",
)
def test_viewer_browser_workloads(
    live_server: LiveServer,
    django_user_model: type[User],
) -> None:
    """Keep browser timing separate from the serial backend suite and its load."""
    manifest: Path = (
        BASE_DIR / "speleodb/common/static/speleodb/vite/.vite/manifest.json"
    )
    assert manifest.is_file()
    password: str = secrets.token_urlsafe(32)
    user: User = django_user_model.objects.create_user(
        email="viewer-browser@example.test",
        name="Viewer Browser",
        password=password,
    )
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
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
    with subprocess.Popen(  # noqa: S603 - fixed root script
        command,
        cwd=BASE_DIR,
        env=browser_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=1800)
        finally:
            if process.poll() is None:
                # Bun, Playwright and its browser workers share this new group.
                # A timeout/interruption must not leave renderer workers alive.
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
    assert process.returncode == 0, stdout + stderr
