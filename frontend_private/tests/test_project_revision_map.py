"""Historical map links select one authorized source revision."""

from __future__ import annotations

import re
from contextlib import closing
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from http.client import HTTPConnection
from http.client import HTTPSConnection
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import orjson
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from rest_framework import status

from frontend_private.tests.controller_context import controller_context
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v2.tests.factories import TeamProjectPermissionFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import ProjectCommit
from speleodb.testing.gitlab_pool import canonical_project
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from collections.abc import Generator

    from django.test import Client

    from speleodb.surveys.models import Project


@pytest.fixture
def revisions(db: None) -> Generator[tuple[Project, ProjectGeoJSON, ProjectGeoJSON]]:
    project = canonical_project(PermissionLevel.WEB_VIEWER)
    artifacts: list[ProjectGeoJSON] = []
    for index, letter in enumerate(("a", "b")):
        commit = ProjectCommit.objects.create(
            id=letter * 40,
            project=project,
            author_name="Diver",
            author_email="diver@example.com",
            message="</script><script>bad</script>",
            authored_date=timezone.now() + timedelta(days=index),
        )
        artifacts.append(
            ProjectGeoJSON.objects.create(
                project=project,
                commit=commit,
                file=SimpleUploadedFile(
                    "survey.json",
                    orjson.dumps(
                        {
                            "type": "FeatureCollection",
                            "features": [
                                {
                                    "type": "Feature",
                                    "properties": {},
                                    "geometry": {
                                        "type": "Point",
                                        "coordinates": [index, index],
                                    },
                                }
                            ],
                        }
                    ),
                ),
            )
        )
    yield project, artifacts[0], artifacts[1]
    for artifact in artifacts:
        artifact.file.delete(save=False)


@pytest.mark.django_db
def test_map_selects_exact_older_artifact(
    client: Client,
    revisions: tuple[Project, ProjectGeoJSON, ProjectGeoJSON],
) -> None:
    project, older, newer = revisions
    user = UserFactory.create()
    UserProjectPermissionFactory.create(
        project=project, target=user, level=PermissionLevel.READ_ONLY
    )
    client.force_login(user)
    response = client.get(
        f"/private/project/{project.pk}/revisions/{older.commit_id}/map/"
    )
    assert response.status_code == status.HTTP_200_OK
    context = controller_context(response.content.decode(), "project-revision-map")
    assert context["commitSha"] == older.commit_id
    assert context["artifactRevision"] == older.geojson_revision
    data = context["project"]
    assert isinstance(data, dict)
    signed_url = data["geojson_file"]
    assert isinstance(signed_url, str)
    assert older.file.name is not None
    assert newer.file.name is not None
    assert older.file.name in signed_url
    assert newer.file.name not in signed_url
    url = urlsplit(signed_url)
    assert url.scheme in {"http", "https"}
    assert url.hostname
    connection_type = HTTPSConnection if url.scheme == "https" else HTTPConnection
    with closing(connection_type(url.hostname, url.port, timeout=10)) as connection:
        connection.request("GET", url.path + (f"?{url.query}" if url.query else ""))
        with connection.getresponse() as downloaded:
            assert downloaded.status == status.HTTP_200_OK
            assert orjson.loads(downloaded.read())["features"][0]["geometry"][
                "coordinates"
            ] == [0, 0]
    assert "private" in response["Cache-Control"]
    assert "no-store" in response["Cache-Control"]
    assert "</script><script>bad</script>" not in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "level",
    [
        PermissionLevel.READ_ONLY,
        PermissionLevel.READ_AND_WRITE,
        PermissionLevel.ADMIN,
    ],
)
def test_map_accepts_allowed_levels_and_uppercase_full_sha(
    client: Client,
    revisions: tuple[Project, ProjectGeoJSON, ProjectGeoJSON],
    level: PermissionLevel,
) -> None:
    project, older, _ = revisions
    user = UserFactory.create()
    UserProjectPermissionFactory.create(project=project, target=user, level=level)
    client.force_login(user)
    response = client.get(
        f"/private/project/{project.pk}/revisions/{older.commit_id.upper()}/map/"
    )
    assert response.status_code == status.HTTP_200_OK
    context = controller_context(response.content.decode(), "project-revision-map")
    assert context["commitSha"] == older.commit_id


@pytest.mark.django_db
def test_map_requires_login_and_current_permission(
    client: Client,
    revisions: tuple[Project, ProjectGeoJSON, ProjectGeoJSON],
) -> None:
    project, older, _ = revisions
    url = f"/private/project/{project.pk}/revisions/{older.commit_id}/map/"
    assert client.get(url).status_code == status.HTTP_302_FOUND
    user = UserFactory.create()
    client.force_login(user)
    assert client.get(url).status_code == status.HTTP_403_FORBIDDEN
    grant = UserProjectPermissionFactory.create(
        project=project, target=user, level=PermissionLevel.READ_ONLY
    )
    assert client.get(url).status_code == status.HTTP_200_OK
    grant.is_active = False
    grant.save()
    assert client.get(url).status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_map_team_access_and_inactive_membership(
    client: Client,
    revisions: tuple[Project, ProjectGeoJSON, ProjectGeoJSON],
) -> None:
    project, older, _ = revisions
    user = UserFactory.create()
    membership = SurveyTeamMembershipFactory.create(user=user)
    TeamProjectPermissionFactory.create(
        project=project, target=membership.team, level=PermissionLevel.READ_ONLY
    )
    client.force_login(user)
    url = f"/private/project/{project.pk}/revisions/{older.commit_id}/map/"
    assert client.get(url).status_code == status.HTTP_200_OK
    membership.is_active = False
    membership.save()
    assert client.get(url).status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_missing_and_cross_project_artifacts_never_fall_back(
    client: Client,
    revisions: tuple[Project, ProjectGeoJSON, ProjectGeoJSON],
) -> None:
    project, older, _ = revisions
    user = UserFactory.create()
    UserProjectPermissionFactory.create(
        project=project, target=user, level=PermissionLevel.READ_ONLY
    )
    other = ProjectFactory.create(created_by=user.email)
    UserProjectPermissionFactory.create(
        project=other, target=user, level=PermissionLevel.READ_ONLY
    )
    client.force_login(user)
    for project_id, sha in [
        (other.pk, older.commit_id),
        (project.pk, "c" * 40),
        (project.pk, "a" * 8),
        (project.pk, "invalid"),
    ]:
        assert (
            client.get(
                f"/private/project/{project_id}/revisions/{sha}/map/"
            ).status_code
            == status.HTTP_404_NOT_FOUND
        )
    old_sha = older.commit_id
    older.delete()
    response = client.get(f"/private/project/{project.pk}/revisions/{old_sha}/map/")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Map unavailable" in response.content.decode()
    assert (
        'data-speleodb-controller="project-revision-map"'
        not in response.content.decode()
    )
    response = client.get(
        reverse("private:project_revisions", kwargs={"project_id": project.pk})
    )
    assert old_sha not in response.context["revision_map_urls"]
    assert set(response.context["revision_map_urls"]) == {"b" * 40}
    other_history = client.get(
        reverse("private:project_revisions", kwargs={"project_id": other.pk})
    )
    assert other_history.context["revision_map_urls"] == {}
    assert 'class="revision-history-map' not in other_history.content.decode()


@pytest.mark.django_db
def test_history_main_map_action_opens_latest_non_creation_commit(
    client: Client,
    revisions: tuple[Project, ProjectGeoJSON, ProjectGeoJSON],
) -> None:
    project, _, newer = revisions
    ProjectCommit.objects.create(
        id="e" * 40,
        project=project,
        authored_date=newer.commit.authored_date + timedelta(days=1),
        author_name="SpeleoDB",
        author_email="contact@speleodb.org",
        message="[Automated] Project Creation",
    )
    user = UserFactory.create()
    UserProjectPermissionFactory.create(
        project=project, target=user, level=PermissionLevel.READ_ONLY
    )
    client.force_login(user)
    response = client.get(
        reverse("private:project_revisions", kwargs={"project_id": project.pk})
    )
    expected_url = reverse(
        "private:project_revision_map",
        kwargs={"project_id": project.pk, "hexsha": newer.commit_id},
    )
    main_action = re.search(
        r'<a\b[^>]*class="revision-history-map[^>]*>', response.content.decode()
    )
    assert main_action is not None
    assert f'href="{expected_url}"' in main_action.group()


@pytest.mark.django_db
def test_webviewer_cannot_open_historical_map(
    client: Client,
    revisions: tuple[Project, ProjectGeoJSON, ProjectGeoJSON],
) -> None:
    project, older, _ = revisions
    user = UserFactory.create()
    UserProjectPermissionFactory.create(
        project=project, target=user, level=PermissionLevel.WEB_VIEWER
    )
    client.force_login(user)
    response = client.get(
        f"/private/project/{project.pk}/revisions/{older.commit_id}/map/"
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert (
        'data-speleodb-controller="project-revision-map"'
        not in response.content.decode()
    )


@pytest.mark.django_db
def test_map_history_orders_all_project_revisions_and_selects_exact_link(
    client: Client,
    revisions: tuple[Project, ProjectGeoJSON, ProjectGeoJSON],
) -> None:
    project, older, newer = revisions
    missing = ProjectCommit.objects.create(
        id="c" * 40,
        project=project,
        authored_date=older.commit.authored_date - timedelta(days=1),
        author_name="Diver",
        author_email="diver@example.com",
        message="[Automated] Project Creation",
    )
    ProjectCommit.objects.create(
        id="e" * 40,
        project=project,
        authored_date=older.commit.authored_date - timedelta(days=2),
        author_name="SpeleoDB",
        author_email="contact@speleodb.org",
        message="[Automated] Project Creation",
    )
    user = UserFactory.create()
    other = ProjectFactory.create(created_by=user.email)
    ProjectCommit.objects.create(
        id="d" * 40,
        project=other,
        authored_date=timezone.now(),
        author_name="Diver",
        author_email="diver@example.com",
        message="Other project",
    )
    UserProjectPermissionFactory.create(
        project=project, target=user, level=PermissionLevel.READ_ONLY
    )
    client.force_login(user)
    selected_url = reverse(
        "private:project_revision_map",
        kwargs={"project_id": project.pk, "hexsha": older.commit_id},
    )
    response = client.get(selected_url)
    rendered = response.content.decode()
    main_content = rendered.split("<main", 1)[1].split("</main>", 1)[0]
    visible_text = strip_tags(main_content)
    assert 'aria-disabled="true"' in main_content
    assert "Project History" in visible_text
    assert "Viewing" not in visible_text
    authors = re.findall(
        r'<span class="historical-revision-author">([^<]+)</span>', main_content
    )
    assert authors == ["by Diver", "by Diver", "by Diver"]
    assert older.commit_id not in visible_text
    assert newer.commit_id not in visible_text
    assert "&lt;/script&gt;" in main_content
    assert "</script><script>bad</script>" not in main_content
    selected_link = re.search(r'<a\b[^>]*aria-current="page"[^>]*>', main_content)
    assert selected_link is not None
    assert f'href="{selected_url}"' in selected_link.group()
    rows = response.context["revisions"]
    assert [row["date"] for row in rows] == [
        newer.commit.authored_date,
        older.commit.authored_date,
        missing.authored_date,
    ]
    assert [row["available"] for row in rows] == [True, True, False]
    assert [row["selected"] for row in rows] == [False, True, False]
    assert rows[1]["url"] == selected_url
    assert rows[2]["message"] == missing.message
    next_response = client.get(rows[0]["url"])
    assert [row["selected"] for row in next_response.context["revisions"]] == [
        True,
        False,
        False,
    ]
    next_context = controller_context(
        next_response.content.decode(), "project-revision-map"
    )
    assert next_context["commitSha"] == newer.commit_id


@pytest.mark.django_db
def test_history_supplies_exact_artifacts_for_in_place_switching(
    client: Client,
    revisions: tuple[Project, ProjectGeoJSON, ProjectGeoJSON],
) -> None:
    project, older, newer = revisions
    user = UserFactory.create()
    UserProjectPermissionFactory.create(
        project=project, target=user, level=PermissionLevel.READ_ONLY
    )
    client.force_login(user)
    response = client.get(
        reverse(
            "private:project_revision_map",
            kwargs={"project_id": project.pk, "hexsha": older.commit_id},
        )
    )
    rows = response.context["revisions"]
    assert [row["commit_sha"] for row in rows] == [newer.commit_id, older.commit_id]
    for row, artifact in zip(rows, (newer, older), strict=True):
        assert row["artifact_revision"] == artifact.geojson_revision
        assert artifact.file.name is not None
        assert artifact.file.name in urlsplit(row["geojson_url"]).path
    context = controller_context(response.content.decode(), "project-revision-map")
    assert isinstance(context["project"], dict)
    assert context["project"]["geojson_file"] == rows[1]["geojson_url"]


@pytest.mark.django_db
def test_playback_context_preserves_metadata_availability_and_equal_date_order(
    client: Client,
    revisions: tuple[Project, ProjectGeoJSON, ProjectGeoJSON],
) -> None:
    project, older, newer = revisions
    authored_date = datetime(2024, 5, 15, 1, 2, 3, tzinfo=UTC)
    message = "Extended eastern passage. " * 8 + '</script><script>bad</script>"'
    author = "A long author name " * 8 + '<div>"&'
    missing = ProjectCommit.objects.create(
        id="c" * 40,
        project=project,
        authored_date=authored_date,
        author_name="Diver",
        author_email="diver@example.com",
        message="Map not generated",
    )
    ProjectCommit.objects.filter(project=project).update(
        authored_date=authored_date, creation_date=authored_date
    )
    ProjectCommit.objects.filter(pk=newer.commit_id).update(
        message=message, author_name=author
    )
    user = UserFactory.create()
    UserProjectPermissionFactory.create(
        project=project, target=user, level=PermissionLevel.READ_ONLY
    )
    client.force_login(user)
    with timezone.override("America/Cancun"):
        response = client.get(
            reverse(
                "private:project_revision_map",
                kwargs={"project_id": project.pk, "hexsha": older.commit_id},
            )
        )
    assert response.status_code == status.HTTP_200_OK
    html = response.content.decode()
    context = controller_context(html, "project-revision-map")
    playback = context["revisions"]
    assert isinstance(playback, list)
    assert [row["commitSha"] for row in playback] == [
        missing.pk,
        newer.commit_id,
        older.commit_id,
    ]
    unavailable, latest, selected = playback
    assert unavailable["available"] is False
    assert unavailable["geojsonUrl"] is None
    assert unavailable["artifactRevision"] is None
    assert latest["available"] is True
    assert latest["message"] == message
    assert latest["authorName"] == author
    assert latest["dateLabel"] == "May 14, 2024"
    assert latest["displayDateLabel"] == "May 14, 2024 at 20:02"
    assert latest["timestampLabel"] == "May 14, 2024 at 20:02:03 -0500"
    assert latest["artifactRevision"] == newer.geojson_revision
    assert newer.file.name is not None
    assert newer.file.name in urlsplit(latest["geojsonUrl"]).path
    assert selected["url"] == response.wsgi_request.path
    assert "</script><script>bad</script>" not in html


@pytest.mark.django_db
def test_initial_revision_metadata_survives_exclusion_from_timeline(
    client: Client,
    revisions: tuple[Project, ProjectGeoJSON, ProjectGeoJSON],
) -> None:
    project, older, newer = revisions
    ProjectCommit.objects.filter(pk=older.commit_id).update(
        author_name="SpeleoDB", message="[Automated] Project Creation"
    )
    user = UserFactory.create()
    UserProjectPermissionFactory.create(
        project=project, target=user, level=PermissionLevel.READ_ONLY
    )
    client.force_login(user)
    response = client.get(
        reverse(
            "private:project_revision_map",
            kwargs={"project_id": project.pk, "hexsha": older.commit_id},
        )
    )
    assert response.status_code == status.HTTP_200_OK
    context = controller_context(response.content.decode(), "project-revision-map")
    selected = context["selectedRevision"]
    assert isinstance(selected, dict)
    assert selected["commitSha"] == older.commit_id
    assert selected["artifactRevision"] == older.geojson_revision
    assert selected["message"] == "[Automated] Project Creation"
    assert selected["authorName"] == "SpeleoDB"
    assert selected["url"] == response.wsgi_request.path
    assert older.file.name is not None
    assert isinstance(selected["geojsonUrl"], str)
    assert older.file.name in urlsplit(selected["geojsonUrl"]).path
    playback = context["revisions"]
    assert isinstance(playback, list)
    assert [row["commitSha"] for row in playback] == [newer.commit_id]
