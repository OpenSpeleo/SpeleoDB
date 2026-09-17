"""Account names remain nonblank through application and database writes."""

from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import connection
from django.db import transaction
from django.test.utils import CaptureQueriesContext

from speleodb.users.models import User
from speleodb.utils.user_identity import USER_NAME_NONBLANK_PATTERN
from speleodb.utils.user_identity import has_user_name
from speleodb.utils.user_identity import validate_user_name

if TYPE_CHECKING:
    from typing import Literal


PYTHON_WHITESPACE: str = (
    "\t\n\v\f\r\x1c\x1d\x1e\x1f \x85\xa0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000"
)
INVALID_NAMES: tuple[str | None, ...] = (
    None,
    "",
    " \t\r\n ",
    *PYTHON_WHITESPACE,
    PYTHON_WHITESPACE,
)
VALID_NAMES: tuple[str, ...] = (
    "Ada Lovelace",
    "Élodie D'Arcy",
    "李明",
    "أحمد علي",
    " \tRenée\u3000",
    "... <>",
    "NO NAME",
)


def test_name_policy_covers_exactly_python_unicode_whitespace() -> None:
    whitespace: set[str] = {
        chr(codepoint)
        for codepoint in range(sys.maxunicode + 1)
        if chr(codepoint).isspace()
    }
    assert set(PYTHON_WHITESPACE) == whitespace
    pattern: re.Pattern[str] = re.compile(USER_NAME_NONBLANK_PATTERN)
    assert all(pattern.search(character) is None for character in whitespace)
    assert all(pattern.search(f"{character}A") is not None for character in whitespace)


@pytest.mark.parametrize("name", INVALID_NAMES)
def test_name_policy_rejects_blank_names(name: str | None) -> None:
    assert not has_user_name(name)
    with pytest.raises(ValidationError, match="A name is required") as error:
        validate_user_name(name)
    assert error.value.code == "blank"


@pytest.mark.parametrize("name", VALID_NAMES)
def test_name_policy_preserves_valid_names(name: str) -> None:
    assert has_user_name(name)
    validate_user_name(name)


def _write_name_without_model_validation(
    user: User,
    name: str | None,
    operation: Literal["update", "bulk_create", "bulk_update", "sql"],
) -> None:
    match operation:
        case "update":
            User.objects.filter(pk=user.pk).update(name=name)
        case "bulk_create":
            unnamed_user: User = User(email="bulk-unnamed@example.com")
            setattr(unnamed_user, "name", name)  # noqa: B010
            User.objects.bulk_create([unnamed_user])
        case "bulk_update":
            setattr(user, "name", name)  # noqa: B010
            User.objects.bulk_update([user], ["name"])
        case "sql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE users_user SET name = %s WHERE id = %s",
                    [name, user.pk],
                )


@pytest.mark.django_db
class TestUserNameWrites:
    def test_missing_name_cannot_be_saved(self) -> None:
        with pytest.raises(ValidationError) as error:
            User.objects.create(email="unnamed@example.com")
        assert "name" in error.value.message_dict
        assert not User.objects.filter(email="unnamed@example.com").exists()

    @pytest.mark.parametrize("name", INVALID_NAMES)
    def test_invalid_names_cannot_be_saved(self, name: str | None) -> None:
        unnamed_user: User = User(email="unnamed@example.com")
        setattr(unnamed_user, "name", name)  # noqa: B010
        with pytest.raises(ValidationError) as error:
            unnamed_user.save()
        assert "name" in error.value.message_dict
        assert not User.objects.filter(email="unnamed@example.com").exists()

    @pytest.mark.parametrize("name", INVALID_NAMES)
    def test_model_field_rejects_blank_names(self, name: str | None) -> None:
        with pytest.raises(ValidationError):
            User._meta.get_field("name").clean(name, None)  # noqa: SLF001

    @pytest.mark.parametrize("name", VALID_NAMES)
    def test_valid_names_round_trip_unchanged(self, name: str) -> None:
        user: User = User.objects.create(email="named@example.com", name=name)
        user.refresh_from_db()
        assert user.name == name

    @pytest.mark.parametrize("partial", [False, True])
    @pytest.mark.parametrize("name", [None, "", " \t\n", PYTHON_WHITESPACE])
    def test_name_changes_are_validated(
        self, user: User, name: str | None, *, partial: bool
    ) -> None:
        original_name: str = user.name
        setattr(user, "name", name)  # noqa: B010
        with pytest.raises(ValidationError) as error:
            user.save(update_fields=iter(["name"]) if partial else None)
        assert "name" in error.value.message_dict
        user.refresh_from_db()
        assert user.name == original_name

    def test_unrelated_partial_save_does_not_validate_name(self, user: User) -> None:
        original_name: str = user.name
        user.name = ""
        user.is_beta_tester = True
        with CaptureQueriesContext(connection) as queries:
            user.save(update_fields=["is_beta_tester"])
        assert len(queries) == 1
        user.refresh_from_db()
        assert user.is_beta_tester
        assert user.name == original_name

    def test_empty_update_fields_remain_a_noop(self, user: User) -> None:
        original_name: str = user.name
        user.name = ""
        with CaptureQueriesContext(connection) as queries:
            user.save(update_fields=[])
        assert len(queries) == 0
        user.refresh_from_db()
        assert user.name == original_name

    @pytest.mark.parametrize("partial", [False, True])
    def test_deferred_name_is_not_loaded_for_unrelated_save(
        self, user: User, *, partial: bool
    ) -> None:
        deferred_user: User = User.objects.only("id", "is_beta_tester").get(pk=user.pk)
        deferred_user.is_beta_tester = True
        with CaptureQueriesContext(connection) as queries:
            deferred_user.save(update_fields=["is_beta_tester"] if partial else None)
        assert len(queries) == 1
        assert "name" in deferred_user.get_deferred_fields()
        user.refresh_from_db()
        assert user.is_beta_tester

    def test_explicitly_assigned_deferred_name_is_validated(self, user: User) -> None:
        deferred_user: User = User.objects.only("id").get(pk=user.pk)
        deferred_user.name = ""
        with pytest.raises(ValidationError):
            deferred_user.save()

    @pytest.mark.parametrize("name", [None, "", " \t\n", PYTHON_WHITESPACE])
    @pytest.mark.parametrize(
        "operation", ["update", "bulk_create", "bulk_update", "sql"]
    )
    def test_database_rejects_writes_bypassing_model_validation(
        self,
        user: User,
        name: str | None,
        operation: Literal["update", "bulk_create", "bulk_update", "sql"],
    ) -> None:
        original_name: str = user.name
        constraint: str = (
            "NOT NULL|not-null" if name is None else "users_user_name_nonblank"
        )
        with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
            _write_name_without_model_validation(user, name, operation)
        user.refresh_from_db()
        assert user.name == original_name
        assert not User.objects.filter(email="bulk-unnamed@example.com").exists()

    @pytest.mark.parametrize("name", tuple(PYTHON_WHITESPACE))
    def test_database_rejects_every_python_whitespace_character(
        self, user: User, name: str
    ) -> None:
        with (
            pytest.raises(IntegrityError, match="users_user_name_nonblank"),
            transaction.atomic(),
        ):
            User.objects.filter(pk=user.pk).update(name=name)
