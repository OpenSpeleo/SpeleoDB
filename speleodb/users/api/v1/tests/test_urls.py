import random

import pytest
from django.urls import resolve
from django.urls import reverse

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
    ],
)
def test_team_dynamic_urls(name: str, path: str, kwargs: dict | None):
    """
    Test the reverse and resolve for dynamic team-related API URLs.
    """
    path = path.format(**kwargs) if kwargs is not None else path
    assert reverse(name, kwargs=kwargs) == path
    assert resolve(path).view_name == name
