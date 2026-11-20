"""Access tokens for third-party apps can read the user's data under API v2."""

from __future__ import annotations

import base64
import json
import secrets
from contextlib import closing
from functools import partial
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
import requests
from allauth.idp.oidc import models
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms.models import model_to_dict
from django.urls import reverse
from git import Actor
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from speleodb.api.v2.tests.factories import GPSTrackFactory
from speleodb.api.v2.tests.factories import LandmarkFactory
from speleodb.api.v2.tests.factories import ProjectCommitFactory
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import SubSurfaceStationFactory
from speleodb.api.v2.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v2.tests.factories import TeamProjectPermissionFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.geometry_services import create_gis_geometry
from speleodb.gis.models import GISGeometry
from speleodb.gis.models import GPSTrack
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import ProjectGeoJSON
from speleodb.git_engine.gitlab_manager import GitlabManager
from speleodb.git_proxy.tests import packet_line
from speleodb.git_proxy.tests import response_body
from speleodb.surveys.models import FileFormat
from speleodb.testing.gitlab_pool import canonical_project
from speleodb.testing.gitlab_pool import get_pool
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.db.models import Model

    from speleodb.surveys.models import Project
    from speleodb.users.models import User


def access_token(user: User, *scopes: str) -> str:
    website = models.Client.objects.create(name="Survey viewer")
    value = secrets.token_urlsafe(64)
    token = models.Token(client=website, user=user, type=models.Token.Type.ACCESS_TOKEN)
    token.set_value(value)
    token.set_scopes(list(scopes))
    token.save()
    return value


@pytest.fixture
def user() -> User:
    return UserFactory.create()


@pytest.fixture
def bearer(user: User) -> str:
    return access_token(user, "openid", "data:read")


@pytest.fixture
def api(bearer: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {bearer}")
    return client


@pytest.fixture
def project(user: User) -> Project:
    project = canonical_project(created_by=user.email)
    UserProjectPermissionFactory.create(
        project=project, target=user, level=PermissionLevel.ADMIN
    )
    return project


def survey_resources(
    user: User, project: Project, request: pytest.FixtureRequest
) -> list[tuple[str, str, Model]]:
    track = GPSTrackFactory.create(creator=user)
    request.addfinalizer(partial(track.file.delete, save=False))
    return [
        ("projects", "project-detail", project),
        ("landmarks", "landmark-detail", LandmarkFactory.create(owner=user)),
        (
            "subsurface-stations",
            "station-detail",
            SubSurfaceStationFactory.create(project=project, created_by=user.email),
        ),
        ("gps-tracks", "gps-track-detail", track),
        (
            "gis-geometry-list",
            "gis-geometry-detail",
            create_gis_geometry(
                GISGeometry(
                    name="Entrance",
                    geojson={"type": "LineString", "coordinates": [[1, 2], [1.001, 2]]},
                ),
                user,
            ),
        ),
    ]


@pytest.mark.django_db
def test_app_reads_only_accessible_survey_data(
    user: User, api: APIClient, project: Project, request: pytest.FixtureRequest
) -> None:
    visible = survey_resources(user, project, request)
    visible.append(
        ("teams", "team-detail", SurveyTeamMembershipFactory.create(user=user).team)
    )
    outsider = UserFactory.create()
    other_project = ProjectFactory.create(created_by=outsider.email)
    UserProjectPermissionFactory.create(target=outsider, project=other_project)
    survey_resources(outsider, other_project, request)
    SurveyTeamMembershipFactory.create(user=outsider)
    for route, detail_route, item in visible:
        response = api.get(reverse(f"api:v2:{route}"))
        assert response.status_code == HTTPStatus.OK, route
        rows = response.json()["landmarks"] if route == "landmarks" else response.json()
        assert [row["id"] for row in rows] == [str(item.pk)], route
        if isinstance(item, GISGeometry):
            detail = api.get(reverse(f"api:v2:{detail_route}", args=[item.pk]))
            assert detail.json()["geojson"] == item.geojson
        if isinstance(item, GPSTrack):
            with (
                requests.get(rows[0]["file"], timeout=5) as download,
                item.file.open("rb") as stored,
            ):
                download.raise_for_status()
                assert download.content == stored.read()

    # A live token must observe permission changes made after it was issued.
    grant = project.user_permissions.get(target=user)
    grant.deactivate(deactivated_by=user)
    assert api.get(reverse("api:v2:projects")).json() == []
    assert (
        api.get(reverse("api:v2:project-detail", args=[project.pk])).status_code
        == HTTPStatus.FORBIDDEN
    )


@pytest.mark.django_db
def test_app_reads_personal_landmark_collection_on_first_access(
    user: User, api: APIClient
) -> None:
    response = api.get(reverse("api:v2:landmark-collections"))
    assert response.status_code == HTTPStatus.OK
    personal = LandmarkCollection.objects.get(personal_owner=user)
    assert [row["id"] for row in response.json()] == [str(personal.pk)]


@pytest.mark.django_db
def test_app_reads_project_geojson(
    api: APIClient, project: Project, request: pytest.FixtureRequest
) -> None:
    for target in (project, ProjectFactory.create()):
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [1, 2]},
            "properties": {"project": str(target.pk)},
        }
        contents = json.dumps(
            {"type": "FeatureCollection", "features": [feature]}
        ).encode()
        artifact = ProjectGeoJSON.objects.create(
            project=target,
            commit=ProjectCommitFactory.create(project=target),
            file=SimpleUploadedFile(
                "entrance.geojson", contents, content_type="application/geo+json"
            ),
        )
        request.addfinalizer(artifact.delete)
    response = api.get(reverse("api:v2:all-projects-geojson"))
    assert response.status_code == HTTPStatus.OK
    assert [row["id"] for row in response.json()] == [str(project.pk)]
    with requests.get(response.json()[0]["geojson_file"], timeout=5) as download:
        download.raise_for_status()
        assert download.json()["features"][0]["properties"]["project"] == str(
            project.pk
        )


@pytest.mark.django_db
def test_malformed_bearer_cannot_inherit_session_on_profile_read(bearer: str) -> None:
    client = APIClient()
    client.force_login(UserFactory.create())
    client.credentials(HTTP_AUTHORIZATION=f"Bearer\t{bearer}")
    response = client.get(reverse("api:v2:user-detail"))
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.django_db
def test_app_cannot_obtain_or_create_personal_token(api: APIClient, user: User) -> None:
    url = reverse("api:v2:user-auth-token")
    assert api.get(url).status_code == HTTPStatus.FORBIDDEN
    assert not Token.objects.filter(user=user).exists()
    personal = Token.objects.create(user=user)
    response = api.get(url)
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert personal.key.encode() not in response.content


@pytest.mark.django_db
def test_app_scope_and_method_restrictions_even_with_session(
    user: User, api: APIClient
) -> None:
    profile = reverse("api:v2:user-detail")
    assert api.get(reverse("api:v1:projects")).status_code == HTTPStatus.FORBIDDEN
    api.force_login(user)
    response = api.patch(profile, {"name": "Changed by app"}, format="json")
    refreshed = type(user).objects.get(pk=user.pk)
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert refreshed.name == user.name
    for method in (api.head, api.options):
        assert method(profile).status_code == HTTPStatus.FORBIDDEN
    teams = reverse("api:v2:teams")
    assert (
        api.post(
            teams,
            {"name": "New team", "country": "MX", "description": "Survey"},
            format="json",
        ).status_code
        == HTTPStatus.FORBIDDEN
    )
    assert not user.teams.exists()
    assert (
        api.get(reverse("api:v2:user-auth-token")).status_code == HTTPStatus.FORBIDDEN
    )
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token(user, 'openid')}")
    assert api.get(profile).status_code == HTTPStatus.FORBIDDEN


@pytest.mark.django_db
def test_owner_app_cannot_modify_or_delete_survey_resources(
    api: APIClient, user: User, project: Project, request: pytest.FixtureRequest
) -> None:
    for _, route, item in survey_resources(user, project, request):
        url = reverse(f"api:v2:{route}", args=[item.pk])
        item.refresh_from_db()
        before = model_to_dict(item)
        data: dict[str, str | int] = {"name": "Changed by app"}
        if isinstance(item, GISGeometry):
            data["expected_revision"] = item.revision
        else:
            representation = api.get(url).json()
            fields = representation.get("landmark", representation)
            fields.pop("created_by", None)
            assert (
                api.put(url, fields | data, format="json").status_code
                == HTTPStatus.FORBIDDEN
            ), route
        assert (
            api.patch(url, data, format="json").status_code == HTTPStatus.FORBIDDEN
        ), route
        assert api.delete(url).status_code == HTTPStatus.FORBIDDEN, route
        item.refresh_from_db()
        assert model_to_dict(item) == before, route


@pytest.mark.django_db
def test_project_admin_app_cannot_modify_or_delete_grants(
    api: APIClient, project: Project
) -> None:
    user_grant = UserProjectPermissionFactory.create(
        project=project, level=PermissionLevel.READ_ONLY
    )
    team_grant = TeamProjectPermissionFactory.create(
        project=project, level=PermissionLevel.READ_ONLY
    )
    for kind, grant, target in (
        ("user", user_grant, user_grant.target.email),
        ("team", team_grant, str(team_grant.target_id)),
    ):
        url = reverse(f"api:v2:project-{kind}-permissions-detail", args=[project.pk])
        assert (
            api.put(
                url, {kind: target, "level": "READ_AND_WRITE"}, format="json"
            ).status_code
            == HTTPStatus.FORBIDDEN
        )
        assert (
            api.delete(url, {kind: target}, format="json").status_code
            == HTTPStatus.FORBIDDEN
        )
        grant.refresh_from_db()
        assert grant.is_active
        assert grant.level == PermissionLevel.READ_ONLY


@pytest.mark.django_db(transaction=True)
@pytest.mark.skip_if_lighttest
def test_app_git_explorer_clones_project_and_refreshes_revisions(
    api: APIClient, project: Project
) -> None:
    get_pool().prepare(project)
    revision = GitlabManager.get_last_commit_hash(project)
    assert revision is not None
    assert not project.git_repo_dir.exists()
    assert not project.commits.exists()
    response = api.get(
        reverse("api:v2:project-gitexplorer", args=[project.pk, revision])
    )
    assert response.status_code == HTTPStatus.OK
    assert response.data["commit"]["hexsha"] == revision
    assert project.commits.filter(pk=revision).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.skip_if_lighttest
def test_app_cannot_upload_or_push_to_locked_project(
    user: User, api: APIClient, project: Project, bearer: str
) -> None:
    get_pool().prepare(project)
    project.acquire_mutex(user)
    branch = f"refs/heads/{settings.DJANGO_GIT_BRANCH_NAME}"
    with project.git_repo as repo:
        head = repo.git.ls_remote("origin", branch)
        fixture = settings.BASE_DIR / "speleodb/api/v2/tests/artifacts/test_simple.tml"
        upload = SimpleUploadedFile(fixture.name, fixture.read_bytes())
        url = reverse(
            "api:v2:project-upload",
            args=[project.pk, FileFormat.ARIANE_TML.label.lower()],
        )
        assert (
            api.put(
                url,
                {"artifact": upload, "message": "Upload survey"},
                format="multipart",
            ).status_code
            == HTTPStatus.FORBIDDEN
        )
        assert repo.git.ls_remote("origin", branch) == head

        previous = repo.head.commit.hexsha
        (project.git_repo_dir / "survey.txt").write_text("Survey change")
        repo.index.add(["survey.txt"])
        actor = Actor(user.name, user.email)
        candidate = repo.index.commit("Update survey", author=actor, committer=actor)
        pack = repo.git.pack_objects(
            "--stdout", "--all", stdout_as_string=False, strip_newline_in_stdout=False
        )
        command = packet_line(
            f"{previous} {candidate.hexsha} {branch}\x00report-status\n".encode()
        )
        push = command + b"0000" + pack
        credentials = base64.b64encode(f"oauth2:{bearer}".encode()).decode()
        for auth in (f"Bearer {bearer}", f"Basic {credentials}"):
            with closing(
                APIClient().post(
                    reverse("git_service_write", args=[project.pk]),
                    data=push,
                    content_type="application/x-git-receive-pack-request",
                    headers={"Authorization": auth},
                )
            ) as response:
                # The Git proxy reports rejection in a packet even when HTTP is 200.
                assert b"Invalid token." in response_body(response)
        assert repo.git.ls_remote("origin", branch) == head
