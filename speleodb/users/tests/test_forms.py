# -*- coding: utf-8 -*-
"""Module for all Form Tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from speleodb.users.forms import UserAdminChangeForm
from speleodb.users.forms import UserAdminCreationForm

if TYPE_CHECKING:
    from speleodb.users.models import User


class TestUserAdminCreationForm:
    """
    Test class for all tests related to the UserAdminCreationForm
    """

    def test_username_validation_error_msg(self, user: User) -> None:
        """
        Tests UserAdminCreation Form's unique validator functions correctly by testing:
            1) A new user with an existing username cannot be added.
            2) Only 1 error is raised by the UserCreation Form
            3) The desired error message is raised
        """

        # The user already exists,
        # hence cannot be created.
        form = UserAdminCreationForm(
            {
                "email": user.email,
                "name": user.name,
                "password1": user.password,
                "password2": user.password,
            },
        )

        assert not form.is_valid()
        assert len(form.errors) == 1
        assert "email" in form.errors
        assert form.errors["email"][0] == "This email has already been taken."

    @pytest.mark.parametrize("name", [None, "", " \t\n ", "\u00a0\u2003"])
    def test_name_is_required(self, db: None, name: str | None) -> None:
        data: dict[str, str] = {
            "email": "new-user@example.com",
            "password1": "My_R@ndom-P@ssw0rd",
            "password2": "My_R@ndom-P@ssw0rd",
        }
        if name is not None:
            data["name"] = name
        form = UserAdminCreationForm(data)

        assert not form.is_valid()
        assert "name" in form.errors


class TestUserAdminChangeForm:
    @pytest.mark.parametrize("name", ["", " \t\n ", "\u00a0\u2003"])
    def test_name_cannot_be_cleared(self, user: User, name: str) -> None:
        form = UserAdminChangeForm(
            {"email": user.email, "name": name, "country": str(user.country)},
            instance=user,
        )

        assert not form.is_valid()
        assert "name" in form.errors
