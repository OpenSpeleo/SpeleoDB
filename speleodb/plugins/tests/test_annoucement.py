from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from speleodb.common.enums import SurveyPlatformEnum
from speleodb.plugins.models import PublicAnnoucement


@pytest.mark.django_db
class TestPublicAnnouncementModel:
    """
    Test suite for the PublicAnnoucement Django model.
    Covers:
    - Field creation and defaults
    - Choices for 'software'
    - Version validation (SemVer, CalVer)
    - Property getters/setters for 'version'
    - Expiracy date handling
    - __str__ and __repr__ methods
    """

    @pytest.fixture
    def announcement(self) -> PublicAnnoucement:
        """Creates a default valid announcement instance (unsaved)."""
        return PublicAnnoucement(
            title="Test Announcement",
            header="Test Header",
            message="This is a test announcement.",
            software=SurveyPlatformEnum.WEB,
            version="1.2.3",
        )

    # -------------------------
    # Field Tests
    # -------------------------

    def test_creation_with_minimal_fields(self) -> None:
        obj = PublicAnnoucement.objects.create(
            title="Minimal",
            header="Header",
            message="Msg",
            software=SurveyPlatformEnum.ARIANE,
        )
        assert obj.pk is not None
        assert obj.creation_date is not None
        assert obj.modified_date is not None
        assert obj.expiracy_date is None
        assert obj.version == ""
        assert obj.is_active is True

    def test_explicit_version_is_stored(self, announcement: PublicAnnoucement) -> None:
        announcement.full_clean()
        announcement.save()
        assert announcement.version == "1.2.3"

    def test_platform_enum_choices(self) -> None:
        choices = dict(SurveyPlatformEnum.choices)
        assert choices[SurveyPlatformEnum.WEB] == "WEB"
        assert choices[SurveyPlatformEnum.ARIANE] == "ARIANE"

    def test_str_representation(self, announcement: PublicAnnoucement) -> None:
        assert str(announcement) == announcement.title

    def test_repr_representation(self, announcement: PublicAnnoucement) -> None:
        expected = f"<PublicAnnoucement: {announcement.title}>"
        assert repr(announcement) == expected

    # -------------------------
    # Version Validation Tests
    # -------------------------

    @pytest.mark.parametrize("version", ["1.0.0", "2.0.0", "2025.06.01", "2025.6.1"])
    def test_valid_versions(
        self, announcement: PublicAnnoucement, version: str
    ) -> None:
        announcement.version = version
        # Should not raise ValidationError
        announcement.full_clean()

    @pytest.mark.parametrize("version", ["", None])
    def test_empty_versions(
        self, announcement: PublicAnnoucement, version: str | None
    ) -> None:
        announcement.version = version
        announcement.full_clean()
        assert announcement.version == version

    @pytest.mark.parametrize("invalid_version", ["1", "1.2", "2025", "abc", 1234])
    def test_invalid_versions_raise_validation(
        self, announcement: PublicAnnoucement, invalid_version: str | int
    ) -> None:
        announcement.version = invalid_version
        with pytest.raises(ValidationError):
            announcement.full_clean()

    # -------------------------
    # Expiracy Date Tests
    # -------------------------

    def test_expiracy_date_can_be_set(self, announcement: PublicAnnoucement) -> None:
        today = timezone.localdate()
        announcement.expiracy_date = today + timedelta(days=10)
        announcement.full_clean()  # Should pass
        announcement.save()
        assert announcement.expiracy_date == today + timedelta(days=10)

    # -------------------------
    # Timestamp Fields Tests
    # -------------------------

    def test_modified_date_auto_updates(self, announcement: PublicAnnoucement) -> None:
        announcement.save()
        initial_modified = announcement.modified_date

        announcement.title = "Updated Title"
        announcement.save()

        # Allowing for very small timestamp differences
        assert announcement.modified_date >= initial_modified
