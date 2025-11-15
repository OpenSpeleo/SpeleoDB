import pytest
from django.core.exceptions import ValidationError

from speleodb.plugins.models import PluginRelease
from speleodb.plugins.models.platform_base import OperatingSystemEnum
from speleodb.plugins.models.platform_base import SurveyPlatformEnum


@pytest.mark.django_db
class TestPluginReleaseModel:
    @pytest.fixture
    def plugin_release(self) -> PluginRelease:
        """Create a default valid PluginRelease instance (unsaved)."""
        return PluginRelease(
            plugin_version="1.2.3",
            software=SurveyPlatformEnum.WEB,
            min_software_version="3.0.0",
            max_software_version="4.0.0",
            operating_system=OperatingSystemEnum.LINUX,
            changelog="Initial release",
            sha256_hash="a" * 64,
            download_url="https://example.com/download/plugin.zip",
        )

    # -------------------------
    # Field and Choice Tests
    # -------------------------

    def test_creation_with_minimal_fields(self) -> None:
        obj = PluginRelease.objects.create(
            plugin_version="0.1.0",
            software=SurveyPlatformEnum.ARIANE,
            min_software_version="",
            max_software_version="",
            operating_system=OperatingSystemEnum.ANY,
            changelog="Minimal release",
            download_url="https://example.com/download/minimal.zip",
        )
        assert obj.pk is not None
        assert obj.creation_date is not None
        assert obj.modified_date is not None
        # sha256_hash is nullable, so can be None
        assert obj.sha256_hash is None or len(obj.sha256_hash) == 64  # noqa: PLR2004

    def test_enum_choices(self) -> None:
        software_choices = dict(SurveyPlatformEnum.choices)
        operating_system_choices = dict(OperatingSystemEnum.choices)

        assert software_choices[SurveyPlatformEnum.WEB] == "WEB"
        assert software_choices[SurveyPlatformEnum.ARIANE] == "ARIANE"
        assert operating_system_choices[OperatingSystemEnum.LINUX] == "LINUX"
        assert operating_system_choices[OperatingSystemEnum.MACOS] == "MACOS"
        assert operating_system_choices[OperatingSystemEnum.WINDOWS] == "WINDOWS"
        assert operating_system_choices[OperatingSystemEnum.ANY] == "ANY"

    # -------------------------
    # Validation Tests
    # -------------------------

    @pytest.mark.parametrize(
        "sha256",
        [
            "a" * 64,
            "A" * 64,
            "0123456789abcdef" * 4,
            "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
        ],
    )
    def test_valid_sha256_hash(
        self, plugin_release: PluginRelease, sha256: str
    ) -> None:
        plugin_release.sha256_hash = sha256
        plugin_release.full_clean()  # Should not raise
        assert plugin_release.sha256_hash == sha256.lower()

    @pytest.mark.parametrize(
        "invalid_sha",
        [
            "g" * 64,  # invalid hex char
            "a" * 63,  # too short
            "a" * 65,  # too long
            "not-a-valid-sha256",
        ],
    )
    def test_invalid_sha256_hash_raises(
        self, plugin_release: PluginRelease, invalid_sha: str | None
    ) -> None:
        plugin_release.sha256_hash = invalid_sha
        with pytest.raises(ValidationError):
            plugin_release.full_clean()

    # -------------------------
    # String representations
    # -------------------------

    def test_str_representation(self, plugin_release: PluginRelease) -> None:
        expected = (
            f"[{SurveyPlatformEnum(plugin_release.software).label} - "
            f">=3.0.0,<=4.0.0] {plugin_release.plugin_version}: "
            f"{plugin_release.download_url}"
        )
        assert str(plugin_release) == expected

    def test_str_representation_min_only(self) -> None:
        release = PluginRelease(
            plugin_version="1.0.0",
            software=SurveyPlatformEnum.WEB,
            min_software_version="2.0.0",
            max_software_version="",
            download_url="https://example.com/plugin.zip",
        )
        expected = "[WEB - >=2.0.0] 1.0.0: https://example.com/plugin.zip"
        assert str(release) == expected

    def test_str_representation_max_only(self) -> None:
        release = PluginRelease(
            plugin_version="1.0.0",
            software=SurveyPlatformEnum.WEB,
            min_software_version="",
            max_software_version="3.0.0",
            download_url="https://example.com/plugin.zip",
        )
        expected = "[WEB - <=3.0.0] 1.0.0: https://example.com/plugin.zip"
        assert str(release) == expected

    def test_str_representation_no_version(self) -> None:
        release = PluginRelease(
            plugin_version="1.0.0",
            software=SurveyPlatformEnum.WEB,
            min_software_version="",
            max_software_version="",
            download_url="https://example.com/plugin.zip",
        )
        expected = "[WEB] 1.0.0: https://example.com/plugin.zip"
        assert str(release) == expected

    def test_repr_representation(self, plugin_release: PluginRelease) -> None:
        expected = f"<PluginRelease: {plugin_release}>"
        assert repr(plugin_release) == expected
