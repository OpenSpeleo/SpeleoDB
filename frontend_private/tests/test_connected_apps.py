from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from secrets import token_urlsafe
from typing import TYPE_CHECKING

import pytest
from allauth.idp.oidc import models
from django.urls import reverse
from django.utils import timezone

from speleodb.users.tests.factories import VerifiedUserFactory

if TYPE_CHECKING:
    from django.test import Client

    from speleodb.users.models import User


@pytest.mark.django_db
def test_revoke_invalidates_only_this_users_grants_for_one_app(client: Client) -> None:
    user = VerifiedUserFactory.create(email="diver-a@example.test")
    other_user = VerifiedUserFactory.create(email="diver-b@example.test")
    app = models.Client.objects.create(
        name="Survey notebook",
        redirect_uris=(
            "https://survey.example:8443/auth/callback\n"
            "https://SURVEY.example:8443/another/callback"
        ),
    )
    other_app = models.Client.objects.create(
        name="Dive planner",
        redirect_uris="https://planner.example/callback\nhttps://auth.example/callback",
    )
    expired_app = models.Client.objects.create(name="Retired website")

    def issue(
        owner: User,
        website: models.Client,
        kind: models.Token.Type,
        scopes: str = "openid",
    ) -> str:
        value = token_urlsafe(32)
        token = models.Token(client=website, user=owner, type=kind, scopes=scopes)
        token.set_value(value)
        token.save()
        return value

    access = issue(user, app, models.Token.Type.ACCESS_TOKEN)
    refresh = issue(user, app, models.Token.Type.REFRESH_TOKEN, "openid\ndata:read")
    code = issue(user, app, models.Token.Type.AUTHORIZATION_CODE)
    other_website_access = issue(user, other_app, models.Token.Type.ACCESS_TOKEN)
    other_user_access = issue(other_user, app, models.Token.Type.ACCESS_TOKEN, "email")
    expired = issue(user, expired_app, models.Token.Type.ACCESS_TOKEN)
    models.Token.objects.by_value(expired).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )
    client.force_login(user)
    profile = reverse("private:user_profile")
    connections = "/private/connected-apps/"
    profile_html = client.get(profile).content.decode()
    assert app.name not in profile_html
    assert f'href="{connections}"' in profile_html
    assert (
        f'href="{connections}"'
        in client.get(reverse("private:user_preferences")).content.decode()
    )
    response = client.get(connections)
    assert response.status_code == HTTPStatus.OK
    html = response.content.decode()
    assert html.count(f'value="{app.pk}"') == 1
    assert 'href="https://survey.example:8443"' in html
    assert "planner.example" not in html
    assert "auth.example" not in html
    assert "/auth/callback" not in html
    assert "Read survey data" in html
    assert "Email address" not in html
    assert other_app.name in html
    assert expired_app.name not in html

    response = client.post(connections, {"revoke_client": app.pk}, follow=True)
    assert response.redirect_chain == [(connections, 302)]
    assert app.name not in response.content.decode()
    assert other_app.name in response.content.decode()
    for value in (access, refresh, code):
        assert not models.Token.objects.by_value(value).exists()
    assert models.Token.objects.by_value(other_user_access).exists()
    assert models.Token.objects.by_value(other_website_access).exists()

    last = client.post(connections, {"revoke_client": other_app.pk}, follow=True)
    assert last.status_code == HTTPStatus.OK
    assert other_app.name not in last.content.decode()
    profile_html = client.get(profile).content.decode()
    assert f'href="{connections}"' not in profile_html
    assert "Connected Apps" not in profile_html
