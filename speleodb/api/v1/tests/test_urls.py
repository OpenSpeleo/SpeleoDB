import random
import uuid

import pytest
from django.urls import resolve
from django.urls import reverse

from speleodb.surveys.models import Format
from speleodb.surveys.models import Project


@pytest.mark.parametrize(
    ("name", "path", "kwargs"),
    [
        ("api:v1:create_project", "/api/v1/project/", None),
        (
            "api:v1:one_project_apiview",
            "/api/v1/project/{id}/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:list_project_user_permissions",
            "/api/v1/project/{id}/permissions/user/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:list_project_team_permissions",
            "/api/v1/project/{id}/permissions/team/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:project_user_permission",
            "/api/v1/project/{id}/permission/user/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:project_team_permission",
            "/api/v1/project/{id}/permission/team/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:acquire_project",
            "/api/v1/project/{id}/acquire/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:release_project",
            "/api/v1/project/{id}/release/",
            {"id": uuid.uuid4()},
        ),
    ],
)
def test_url_resolution(name: str, path: str, kwargs: dict | None):
    """
    Tests URL resolution and path generation for various endpoints.
    """
    path = path if kwargs is None else path.format(**kwargs)

    # Assert that reverse matches the expected path
    assert reverse(name, kwargs=kwargs) == path

    # Assert that resolve matches the correct view name
    assert resolve(path).view_name == name


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


# ================================= USER APIs ================================= #


@pytest.mark.parametrize(
    ("name", "path"),
    [
        ("api:v1:auth_token", "/api/v1/user/auth-token/"),
        ("api:v1:user_info", "/api/v1/user/info/"),
        ("api:v1:update_user_password", "/api/v1/user/password/"),
    ],
)
def test_user_api_urls(name: str, path: str):
    """
    Test the reverse and resolve for user-related API URLs.
    """
    assert reverse(name) == path
    assert resolve(path).view_name == name


# ================================= TEAM APIs ================================= #


@pytest.mark.parametrize(
    ("name", "path", "kwargs"),
    [
        ("api:v1:create_team", "/api/v1/team/", None),
        ("api:v1:list_user_teams", "/api/v1/teams/", None),
        (
            "api:v1:one_team_apiview",
            "/api/v1/team/{id}/",
            {"id": random.randint(1, 100)},
        ),
        (
            "api:v1:team_membership",
            "/api/v1/team/{id}/membership/",
            {"id": random.randint(1, 100)},
        ),
        (
            "api:v1:team_list_membership",
            "/api/v1/team/{id}/memberships/",
            {"id": random.randint(1, 100)},
        ),
    ],
)
def test_team_dynamic_urls(name: str, path: str, kwargs: dict | None):
    """
    Test the reverse and resolve for dynamic team-related API URLs.
    """
    path = path.format(**kwargs) if kwargs is not None else path
    assert reverse(name, kwargs=kwargs) == path
    assert resolve(path).view_name == name
