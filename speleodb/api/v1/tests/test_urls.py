# -*- coding: utf-8 -*-

from __future__ import annotations

import random
import string
import uuid
from hashlib import sha1
from typing import Any

import pytest
from django.urls import resolve
from django.urls import reverse

from speleodb.surveys.models import Format
from speleodb.surveys.models import Project


def sha1_hash() -> str:
    rand_str = "".join(random.sample(string.ascii_lowercase, 8))
    return sha1(rand_str.encode("utf-8"), usedforsecurity=False).hexdigest()


@pytest.mark.parametrize(
    ("name", "path", "kwargs"),
    [
        ("api:v1:public-announcements", "/api/v1/announcements/", None),
        ("api:v1:plugin-releases", "/api/v1/plugin_releases/", None),
        ("api:v1:projects", "/api/v1/projects/", None),
        (
            "api:v1:project-detail",
            "/api/v1/projects/{id}/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:project-geojson",
            "/api/v1/projects/{id}/geojson/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:project-revisions",
            "/api/v1/projects/{id}/revisions/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:project-gitexplorer",
            "/api/v1/projects/{id}/git_explorer/{hexsha}/",
            {"id": uuid.uuid4(), "hexsha": sha1_hash()},
        ),
        (
            "api:v1:project-user-permissions",
            "/api/v1/projects/{id}/permissions/user/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:project-team-permissions",
            "/api/v1/projects/{id}/permissions/team/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:project-user-permissions-detail",
            "/api/v1/projects/{id}/permission/user/detail/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:project-team-permissions-detail",
            "/api/v1/projects/{id}/permission/team/detail/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:project-acquire",
            "/api/v1/projects/{id}/acquire/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:project-release",
            "/api/v1/projects/{id}/release/",
            {"id": uuid.uuid4()},
        ),
    ],
)
def test_url_resolution(name: str, path: str, kwargs: dict[str, Any] | None) -> None:
    """
    Tests URL resolution and path generation for various endpoints.
    """
    path = path if kwargs is None else path.format(**kwargs)

    # Assert that reverse matches the expected path
    assert reverse(name, kwargs=kwargs) == path

    # Assert that resolve matches the correct view name
    assert resolve(path).view_name == name


@pytest.mark.parametrize("fileformat", Format.FileFormat.upload_choices)
def test_upload_project(fileformat: str, project: Project) -> None:
    endpoint = reverse(
        "api:v1:project-upload",
        kwargs={"id": project.id, "fileformat": fileformat},
    )
    expected_endpoint = f"/api/v1/projects/{project.id}/upload/{fileformat}/"

    assert endpoint == expected_endpoint, endpoint

    assert resolve(expected_endpoint).view_name == "api:v1:project-upload", resolve(
        expected_endpoint
    ).view_name


@pytest.mark.parametrize("fileformat", Format.FileFormat.download_choices)
def test_download_project(fileformat: str, project: Project) -> None:
    endpoint = reverse(
        "api:v1:project-download",
        kwargs={"id": project.id, "fileformat": fileformat},
    )
    expected_endpoint = f"/api/v1/projects/{project.id}/download/{fileformat}/"

    assert endpoint == expected_endpoint, endpoint

    assert resolve(expected_endpoint).view_name == "api:v1:project-download", resolve(
        expected_endpoint
    ).view_name


@pytest.mark.parametrize("fileformat", Format.FileFormat.download_choices)
def test_download_project_at_hash(fileformat: str, project: Project) -> None:
    hexsha = sha1_hash()
    endpoint = reverse(
        "api:v1:project-download-at-hash",
        kwargs={"id": project.id, "hexsha": hexsha, "fileformat": fileformat},
    )
    expected_endpoint = f"/api/v1/projects/{project.id}/download/{fileformat}/{hexsha}/"

    assert endpoint == expected_endpoint, endpoint

    assert resolve(expected_endpoint).view_name == "api:v1:project-download-at-hash", (
        resolve(expected_endpoint).view_name
    )


# ================================= USER APIs ================================= #


@pytest.mark.parametrize(
    ("name", "path"),
    [
        ("api:v1:user-detail", "/api/v1/user/"),
        ("api:v1:user-auth-token", "/api/v1/user/auth-token/"),
        ("api:v1:user-password-update", "/api/v1/user/password/"),
    ],
)
def test_user_api_urls(name: str, path: str) -> None:
    """
    Test the reverse and resolve for user-related API URLs.
    """
    assert reverse(name) == path
    assert resolve(path).view_name == name


# ================================= TEAM APIs ================================= #


@pytest.mark.parametrize(
    ("name", "path", "kwargs"),
    [
        ("api:v1:teams", "/api/v1/teams/", None),
        (
            "api:v1:team-detail",
            "/api/v1/teams/{id}/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:team-memberships-detail",
            "/api/v1/teams/{id}/memberships/detail/",
            {"id": uuid.uuid4()},
        ),
        (
            "api:v1:team-memberships",
            "/api/v1/teams/{id}/memberships/",
            {"id": uuid.uuid4()},
        ),
    ],
)
def test_team_dynamic_urls(name: str, path: str, kwargs: dict[str, Any] | None) -> None:
    """
    Test the reverse and resolve for dynamic team-related API URLs.
    """
    path = path.format(**kwargs) if kwargs is not None else path
    assert reverse(name, kwargs=kwargs) == path
    assert resolve(path).view_name == name
