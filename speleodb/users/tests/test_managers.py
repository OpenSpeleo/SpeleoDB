# -*- coding: utf-8 -*-

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError

from speleodb.users.models import User


@pytest.mark.django_db
class TestUserManager:
    def test_create_user(self) -> None:
        user = User.objects.create_user(
            email="john@example.com",
            name="John Example",
            password="something-r@nd0m!",  # noqa: S106
        )
        assert user.email == "john@example.com"
        assert not user.is_staff
        assert not user.is_superuser
        assert user.check_password("something-r@nd0m!")
        assert user.username is None

    def test_create_superuser(self) -> None:
        user = User.objects.create_superuser(
            email="admin@example.com",
            name="Administrator",
            password="something-r@nd0m!",  # noqa: S106
        )
        assert user.email == "admin@example.com"
        assert user.is_staff
        assert user.is_superuser
        assert user.username is None

    def test_create_superuser_username_ignored(self) -> None:
        user = User.objects.create_superuser(
            email="test@example.com",
            name="Test Administrator",
            password="something-r@nd0m!",  # noqa: S106
        )
        assert user.username is None


@pytest.mark.django_db
def test_createsuperuser_command() -> None:
    """Ensure createsuperuser command works with our custom manager."""
    out = StringIO()
    command_result = call_command(
        "createsuperuser",
        "--email",
        "henry@example.com",
        "--name",
        "Chuck Norris",
        interactive=False,
        stdout=out,
    )

    assert command_result is None
    assert out.getvalue() == "Superuser created successfully.\n"
    user = User.objects.get(email="henry@example.com")
    assert not user.has_usable_password()
    assert user.name == "Chuck Norris"


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["create_user", "create_superuser"])
@pytest.mark.parametrize("name", [None, "", " \t\r\n", "\u00a0\u3000"])
def test_manager_rejects_blank_name(method: str, name: str | None) -> None:
    with pytest.raises(ValidationError, match="A name is required"):
        getattr(User.objects, method)(email="unnamed@example.com", name=name)
    assert not User.objects.filter(email="unnamed@example.com").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["create_user", "create_superuser"])
def test_manager_requires_name(method: str) -> None:
    with pytest.raises(ValidationError, match="A name is required"):
        getattr(User.objects, method)(email="unnamed@example.com")
    assert not User.objects.filter(email="unnamed@example.com").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("source", ["option", "environment"])
@pytest.mark.parametrize("name", ["", " \t\r\n", "\u00a0\u3000"])
def test_createsuperuser_rejects_blank_name(
    source: str, name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DJANGO_SUPERUSER_NAME", raising=False)
    arguments: list[str] = ["--email", "unnamed@example.com"]
    if source == "option":
        arguments.extend(["--name", name])
    else:
        monkeypatch.setenv("DJANGO_SUPERUSER_NAME", name)
    with pytest.raises(
        CommandError, match=r"--name|cannot be blank|A name is required"
    ):
        call_command("createsuperuser", *arguments, interactive=False)
    assert not User.objects.filter(email="unnamed@example.com").exists()


@pytest.mark.django_db
def test_createsuperuser_requires_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DJANGO_SUPERUSER_NAME", raising=False)
    with pytest.raises(CommandError, match="--name"):
        call_command(
            "createsuperuser", "--email", "unnamed@example.com", interactive=False
        )
    assert not User.objects.filter(email="unnamed@example.com").exists()


@pytest.mark.django_db
def test_createsuperuser_reads_name_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DJANGO_SUPERUSER_NAME", "Environment Administrator")
    call_command(
        "createsuperuser",
        "--email",
        "environment@example.com",
        interactive=False,
        stdout=StringIO(),
    )
    assert (
        User.objects.get(email="environment@example.com").name
        == "Environment Administrator"
    )


@pytest.mark.django_db
def test_createsuperuser_reprompts_for_blank_name() -> None:
    errors: StringIO = StringIO()
    with (
        patch("builtins.input", side_effect=[" \t", "Interactive Administrator"]),
        patch("getpass.getpass", return_value="interactive-strong-password-123!"),
    ):
        call_command(
            "createsuperuser",
            "--email",
            "interactive@example.com",
            interactive=True,
            stdin=None,
            stdout=StringIO(),
            stderr=errors,
        )
    assert "blank" in errors.getvalue()
    assert (
        User.objects.get(email="interactive@example.com").name
        == "Interactive Administrator"
    )
