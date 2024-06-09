from django.urls import resolve
from django.urls import reverse


def test_get_auth_token_url():
    assert reverse("api:v1_users:get_auth_token") == "/api/v1/user/auth-token/"
    assert (
        resolve("/api/v1/user/auth-token/").view_name == "api:v1_users:get_auth_token"
    )


def test_set_user_info_url():
    assert reverse("api:v1_users:set_user_info") == "/api/v1/user/info/"
    assert resolve("/api/v1/user/info/").view_name == "api:v1_users:set_user_info"


def test_set_user_preferences_url():
    assert reverse("api:v1_users:set_user_preferences") == "/api/v1/user/preferences/"
    assert (
        resolve("/api/v1/user/preferences/").view_name
        == "api:v1_users:set_user_preferences"
    )


def test_change_user_password_url():
    assert reverse("api:v1_users:change_user_password") == "/api/v1/user/password/"
    assert (
        resolve("/api/v1/user/password/").view_name
        == "api:v1_users:change_user_password"
    )
