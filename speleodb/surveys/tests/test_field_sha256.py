import hashlib
import os

import pytest
from django.core.exceptions import ValidationError

from speleodb.surveys.fields import Sha256Field
from speleodb.surveys.fields import sha256_validator


class DummyModelSha256:
    # Simulate only the field behavior without DB or model validation
    sha256_field = Sha256Field()

    def __init__(self, sha256: str | None) -> None:
        # Normalize on init to mimic model behavior
        self.sha256 = self.sha256_field.clean(sha256, None)


@pytest.mark.parametrize(
    ("hash_value"),
    [
        "A3C9E1A3BBE4DA7B2F4527B2D314D66AA3EBC24B7A82D5D30C20B0D2BC3FA77F",
        "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        "0123456789abcdef0123456789ABCDEF0123456789abcdef0123456789ABCDEF",
    ],
)
def test_valid_sha256(hash_value: str) -> None:
    instance = DummyModelSha256(sha256=hash_value)
    assert instance.sha256 == hash_value.lower()


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
def test_invalid_sha256(value: str) -> None:
    with pytest.raises(ValidationError):
        _ = DummyModelSha256(sha256=value)

    with pytest.raises(ValidationError):
        sha256_validator(value)


@pytest.mark.parametrize("input_bytes", [os.urandom(32) for _ in range(5)])
def test_random_hashes_with_hashlib(input_bytes: bytes) -> None:
    # Generate SHA256 hex digest (lowercase)
    sha256_hex = hashlib.sha256(input_bytes).hexdigest()

    instance = DummyModelSha256(sha256=sha256_hex.upper())

    # Stored value must be lowercase
    assert instance.sha256 == sha256_hex
