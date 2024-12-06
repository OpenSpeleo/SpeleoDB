from django.urls import resolve
from django.urls import reverse

from speleodb.users.models import SurveyTeam

# ================================= USER APIs ================================= #


def test_auth_token_url():
    assert reverse("api:v1_users:auth_token") == "/api/v1/user/auth-token/"
    assert resolve("/api/v1/user/auth-token/").view_name == "api:v1_users:auth_token"


def test_user_info_url():
    assert reverse("api:v1_users:user_info") == "/api/v1/user/info/"
    assert resolve("/api/v1/user/info/").view_name == "api:v1_users:user_info"


def test_update_user_password_url():
    assert reverse("api:v1_users:update_user_password") == "/api/v1/user/password/"
    assert (
        resolve("/api/v1/user/password/").view_name
        == "api:v1_users:update_user_password"
    )


# ================================= TEAM APIs ================================= #


def test_team_creation_url():
    assert reverse("api:v1_users:create_team") == "/api/v1/team/"
    assert resolve("/api/v1/team/").view_name == "api:v1_users:create_team"


def test_team_view_url(team: SurveyTeam):
    assert (
        reverse("api:v1_users:one_team_apiview", kwargs={"id": team.id})
        == f"/api/v1/team/{team.id}/"
    )
    assert (
        resolve(f"/api/v1/team/{team.id}/").view_name == "api:v1_users:one_team_apiview"
    )


def test_team_membership_url(team: SurveyTeam):
    assert (
        reverse("api:v1_users:team_membership", kwargs={"id": team.id})
        == f"/api/v1/team/{team.id}/membership/"
    )
    assert (
        resolve(f"/api/v1/team/{team.id}/membership/").view_name
        == "api:v1_users:team_membership"
    )
