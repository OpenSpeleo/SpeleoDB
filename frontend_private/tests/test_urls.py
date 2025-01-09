import hashlib
import random
import uuid

import pytest
from django.urls import resolve
from django.urls import reverse


@pytest.mark.parametrize(
    ("name", "path", "kwargs"),
    [
        # General routes
        ("private:user_dashboard", "", None),
        ("private:user_password", "password/", None),
        ("private:user_authtoken", "auth-token/", None),
        ("private:user_feedback", "feedback/", None),
        ("private:user_preferences", "preferences/", None),
        # Teams routes
        ("private:teams", "teams/", None),
        ("private:team_new", "team/new/", None),
        ("private:team_details", "team/{team_id}/", {"team_id": 1}),
        ("private:team_memberships", "team/{team_id}/memberships/", {"team_id": 1}),
        ("private:team_danger_zone", "team/{team_id}/danger_zone/", {"team_id": 1}),
        # Projects routes
        ("private:projects", "projects/", None),
        ("private:project_new", "project/new/", None),
        (
            "private:project_details",
            "project/{project_id}/",
            {"project_id": uuid.uuid4()},
        ),
        (
            "private:project_upload",
            "project/{project_id}/upload/",
            {"project_id": uuid.uuid4()},
        ),
        (
            "private:project_user_permissions",
            "project/{project_id}/permissions/user/",
            {"project_id": uuid.uuid4()},
        ),
        (
            "private:project_team_permissions",
            "project/{project_id}/permissions/team/",
            {"project_id": uuid.uuid4()},
        ),
        (
            "private:project_mutexes",
            "project/{project_id}/mutexes/",
            {"project_id": uuid.uuid4()},
        ),
        (
            "private:project_revisions",
            "project/{project_id}/revisions/",
            {"project_id": uuid.uuid4()},
        ),
        (
            "private:project_revision_explorer",
            "project/{project_id}/browser/{hexsha}/",
            {
                "project_id": uuid.uuid4(),
                "hexsha": hashlib.sha1(  # noqa: S324
                    str(random.random()).encode("utf-8")
                ).hexdigest(),
            },
        ),
        (
            "private:project_danger_zone",
            "project/{project_id}/danger_zone/",
            {"project_id": uuid.uuid4()},
        ),
    ],
)
def test_routes(name: str, path: str, kwargs: dict | None):
    path = f"/private/{path}" if kwargs is None else f"/private/{path.format(**kwargs)}"

    # Test reverse URL generation
    if kwargs:
        assert reverse(name, kwargs=kwargs) == path
    else:
        assert reverse(name) == path

    # Test resolve to view name
    assert resolve(path).view_name == name
