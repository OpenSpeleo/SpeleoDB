import pytest
from django.urls import resolve
from django.urls import reverse

from speleodb.surveys.models import Format
from speleodb.surveys.models import Project


def test_create_project():
    assert reverse("api:v1:create_project") == "/api/v1/project/"
    assert resolve("/api/v1/project/").view_name == "api:v1:create_project"


def test_one_project_apiview(project: Project):
    assert (
        reverse("api:v1:one_project_apiview", kwargs={"id": project.id})
        == f"/api/v1/project/{project.id}/"
    )
    assert (
        resolve(f"/api/v1/project/{project.id}/").view_name
        == "api:v1:one_project_apiview"
    )


def test_list_project_user_permissions(project: Project):
    assert (
        reverse("api:v1:list_project_user_permissions", kwargs={"id": project.id})
        == f"/api/v1/project/{project.id}/permissions/user/"
    )
    assert (
        resolve(f"/api/v1/project/{project.id}/permissions/user/").view_name
        == "api:v1:list_project_user_permissions"
    )


def test_list_project_team_permissions(project: Project):
    assert (
        reverse("api:v1:list_project_team_permissions", kwargs={"id": project.id})
        == f"/api/v1/project/{project.id}/permissions/team/"
    )
    assert (
        resolve(f"/api/v1/project/{project.id}/permissions/team/").view_name
        == "api:v1:list_project_team_permissions"
    )


def test_user_project_permission(project: Project):
    assert (
        reverse("api:v1:project_user_permission", kwargs={"id": project.id})
        == f"/api/v1/project/{project.id}/permission/user/"
    )
    assert (
        resolve(f"/api/v1/project/{project.id}/permission/user/").view_name
        == "api:v1:project_user_permission"
    )


def test_team_project_permission(project: Project):
    assert (
        reverse("api:v1:project_team_permission", kwargs={"id": project.id})
        == f"/api/v1/project/{project.id}/permission/team/"
    )
    assert (
        resolve(f"/api/v1/project/{project.id}/permission/team/").view_name
        == "api:v1:project_team_permission"
    )


def test_acquire_project(project: Project):
    assert (
        reverse("api:v1:acquire_project", kwargs={"id": project.id})
        == f"/api/v1/project/{project.id}/acquire/"
    )
    assert (
        resolve(f"/api/v1/project/{project.id}/acquire/").view_name
        == "api:v1:acquire_project"
    )


def test_release_project(project: Project):
    assert (
        reverse("api:v1:release_project", kwargs={"id": project.id})
        == f"/api/v1/project/{project.id}/release/"
    )
    assert (
        resolve(f"/api/v1/project/{project.id}/release/").view_name
        == "api:v1:release_project"
    )


@pytest.mark.parametrize("fileformat", Format.FileFormat.upload_choices)
def test_upload_project(fileformat: str, project: Project):
    endpoint = reverse(
        "api:v1:upload_project",
        kwargs={"id": project.id, "fileformat": fileformat},
    )
    expected_endpoint = f"/api/v1/project/{project.id}/upload/{fileformat}/"

    assert endpoint == expected_endpoint, endpoint

    assert resolve(expected_endpoint).view_name == "api:v1:upload_project", resolve(
        expected_endpoint
    ).view_name


@pytest.mark.parametrize("fileformat", Format.FileFormat.download_choices)
def test_download_project(fileformat: str, project: Project):
    endpoint = reverse(
        "api:v1:download_project",
        kwargs={"id": project.id, "fileformat": fileformat},
    )
    expected_endpoint = f"/api/v1/project/{project.id}/download/{fileformat}/"

    assert endpoint == expected_endpoint, endpoint

    assert resolve(expected_endpoint).view_name == "api:v1:download_project", resolve(
        expected_endpoint
    ).view_name


@pytest.mark.parametrize("fileformat", Format.FileFormat.download_choices)
def test_download_project_at_hash(fileformat: str, project: Project, sha1_hash: str):
    endpoint = reverse(
        "api:v1:download_project_at_hash",
        kwargs={"id": project.id, "hexsha": sha1_hash, "fileformat": fileformat},
    )
    expected_endpoint = (
        f"/api/v1/project/{project.id}/download/{fileformat}/{sha1_hash}/"
    )

    assert endpoint == expected_endpoint, endpoint

    assert (
        resolve(expected_endpoint).view_name == "api:v1:download_project_at_hash"
    ), resolve(expected_endpoint).view_name
