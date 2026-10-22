import pytest
from django.core.exceptions import ValidationError

from speleodb.surveys.fields import Sha256Field
from speleodb.surveys.fields import sha256_validator


@pytest.mark.parametrize(
    ("hash_value"),
    [
        "A3C9E1A3BBE4DA7B2F4527B2D314D66AA3EBC24B7A82D5D30C20B0D2BC3FA77F",
        "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        "0123456789abcdef0123456789ABCDEF0123456789abcdef0123456789ABCDEF",
    ],
)
def test_valid_sha256(hash_value: str) -> None:
    assert Sha256Field().clean(hash_value, None) == hash_value.lower()


@pytest.mark.parametrize(
    "value",
    [
        "",  # Blank string
        None,  # None
        "abcd",  # Too short
        "g" * 64,  # Invalid hex character
        "f" * 63,  # One char short
        "f" * 65,  # One char too long
    ],
)
def test_invalid_sha256(value: str | None) -> None:
    with pytest.raises(ValidationError):
        Sha256Field().clean(value, None)

    with pytest.raises(ValidationError):
        sha256_validator(value)
