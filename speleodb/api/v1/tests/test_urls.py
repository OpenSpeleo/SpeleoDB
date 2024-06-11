from django.urls import resolve
from django.urls import reverse

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
        resolve(f"/api/v1/project/{project.id}/").view_name == "api:v1:one_project_apiview"
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


def test_upload_project(project: Project):
    assert (
        reverse("api:v1:upload_project", kwargs={"id": project.id})
        == f"/api/v1/project/{project.id}/upload/"
    )
    assert (
        resolve(f"/api/v1/project/{project.id}/upload/").view_name
        == "api:v1:upload_project"
    )


def test_download_project(project: Project):
    assert (
        reverse("api:v1:download_project", kwargs={"id": project.id})
        == f"/api/v1/project/{project.id}/download/"
    )
    assert (
        resolve(f"/api/v1/project/{project.id}/download/").view_name
        == "api:v1:download_project"
    )


def test_download_project_at_hash(project: Project, sha1_hash: str):
    assert (
        reverse(
            "api:v1:download_project_at_hash",
            kwargs={"id": project.id, "commit_sha1": sha1_hash},
        )
        == f"/api/v1/project/{project.id}/download/{sha1_hash}/"
    )
    assert (
        resolve(f"/api/v1/project/{project.id}/download/{sha1_hash}/").view_name
        == "api:v1:download_project_at_hash"
    )


# def test_create_project():
#     assert reverse("api:v1:create_project") == "/api/v1/project/"
#     assert resolve("/api/v1/project/").view_name == "api:v1:create_project"


# def test_create_project():
#     assert reverse("api:v1:create_project") == "/api/v1/project/"
#     assert resolve("/api/v1/project/").view_name == "api:v1:create_project"


# def test_create_project():
#     assert reverse("api:v1:create_project") == "/api/v1/project/"
#     assert resolve("/api/v1/project/").view_name == "api:v1:create_project"


# def test_create_project():
#     assert reverse("api:v1:create_project") == "/api/v1/project/"
#     assert resolve("/api/v1/project/").view_name == "api:v1:create_project"
