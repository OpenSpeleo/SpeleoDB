import pytest
from django.core.exceptions import ValidationError

from speleodb.surveys.fields import VersionField
from speleodb.surveys.fields import version_validator


class DummyModelVersion:
    version = VersionField()

    def __init__(self, version: str | None) -> None:
        # Normalize on init to mimic model behavior
        self.version = self.version.clean(version, None)


@pytest.mark.parametrize(
    "version", ["0.1.0", "1.0.0", "2.5.3", "10.20.30", "9999.9999.9999"]
)
def test_valid_semver(version: str) -> None:
    instance = DummyModelVersion(version=version)
    assert instance.version == version  # type: ignore[comparison-overlap]


@pytest.mark.parametrize(
    "version",
    [
        "2025.06",
        "2025.6",
        "2024.12.31",
        "2023.1.9",
        "2023.09.01",
    ],
)
def test_valid_calver(version: str) -> None:
    instance = DummyModelVersion(version=version)
    assert instance.version == version  # type: ignore[comparison-overlap]


@pytest.mark.parametrize(
    "version",
    [
        "",
        None,
        "1.2",  # Missing patch (SemVer must have 3 parts)
        "1.2.3.4",  # Too many parts for SemVer
        "2025-06-23",  # Invalid separator for CalVer
        "abcd",  # Random garbage
        "2025.13",  # Invalid month for CalVer
        "2025.06.99",  # Invalid day for CalVer
        "not.a.version",
    ],
)
def test_invalid_versions(version: str) -> None:
    with pytest.raises(ValidationError):
        DummyModelVersion(version)

    with pytest.raises(ValidationError):
        version_validator(version)
