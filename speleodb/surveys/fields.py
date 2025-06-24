# -*- coding: utf-8 -*-

from typing import Any

from django.core.validators import RegexValidator
from django.db import models

# https://semver.org/#is-there-a-suggested-regular-expression-regex-to-check-a-semver-string
SEMVER_REGEX = r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$"
CALVER_REGEX = r"^(?P<year>2[0-9]{3})\.(?P<month>1[0-2]|0?[1-9])(\.(?P<day>3[0-1]|[1-2][0-9]|0?[1-9]))?$"  # noqa: E501

version_validator = RegexValidator(
    regex=f"({SEMVER_REGEX})|({CALVER_REGEX})",
    message="Enter a valid SemVer (e.g., 1.2.3) or CalVer (e.g., 2025.06.23)",
)


class VersionField(models.CharField):  # type: ignore[type-arg]
    default_error_messages = {
        "invalid": "Enter a valid version number in SemVer or CalVer format.",
    }
    description = "Version"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_length", 50)
        kwargs.setdefault("validators", [version_validator])
        super().__init__(*args, **kwargs)

    def from_db_value(
        self, value: Any, expression: Any, connection: Any, *args: Any
    ) -> Any:
        """Convert from the database format.
        This should be the inverse of self.get_prep_value()
        """
        return self.to_python(value)

    def value_to_string(self, obj: Any) -> str:
        value = self.value_from_object(obj)
        return value if value else ""


sha256_validator = RegexValidator(
    regex=r"^[a-fA-F0-9]{64}$",
    message="Enter a valid sha256 value",
)


class Sha256Field(models.CharField):  # type: ignore[type-arg]
    default_error_messages = {
        "invalid": "Enter a valid sha256 value.",
    }
    description = "SHA-256"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_length", 64)
        kwargs.setdefault("validators", [sha256_validator])
        super().__init__(*args, **kwargs)

    def to_python(self, value: Any) -> str | None:
        if value is None:
            return value
        return str(value).lower()

    def from_db_value(
        self, value: Any, expression: Any, connection: Any, *args: Any
    ) -> Any:
        """Convert from the database format.
        This should be the inverse of self.get_prep_value()
        """
        return self.to_python(value)

    def get_prep_value(self, value: Any) -> Any:
        value = super().get_prep_value(value)
        return value.lower() if value else value

    def value_to_string(self, obj: Any) -> str:
        value = self.value_from_object(obj)
        return value if value else ""
