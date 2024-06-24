from django.urls import resolve
from django.urls import reverse


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
