# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import tempfile
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from PIL import Image

from frontend_public.models import BoardMember
from frontend_public.models import ExplorerMember
from frontend_public.models import TechnicalMember

if TYPE_CHECKING:
    type PersonAbstract = BoardMember | TechnicalMember | ExplorerMember


class PersonModelTestMixin:
    """Mixin for common person model tests."""

    model_class: type[PersonAbstract]

    def create_test_image(self) -> SimpleUploadedFile:
        """Create a test image file."""
        # Load real image from artifacts
        artifacts_dir = (
            Path(__file__).parent.parent.parent / "speleodb/api/v1/tests/artifacts"
        )
        with (artifacts_dir / "image.jpg").open(mode="rb") as f:
            content = f.read()
        return SimpleUploadedFile("test_photo.jpg", content, content_type="image/jpeg")

    def test_model_creation(self) -> None:
        """Test creating a person instance."""
        photo = self.create_test_image()
        person = self.model_class.objects.create(
            full_name="John Doe",
            title="Test Title",
            description="Test description",
            photo=photo,
        )

        assert person.full_name == "John Doe"
        assert person.title == "Test Title"
        assert person.description == "Test description"
        assert person.photo
        assert person.id is not None
        assert person.creation_date is not None
        assert person.modified_date is not None

    def test_optional_fields(self) -> None:
        """Test that optional fields work correctly."""
        photo = self.create_test_image()
        person = self.model_class.objects.create(
            full_name="Jane Doe",
            title="Another Title",
            description="Another description",
            link_name="LinkedIn",
            link_target="https://linkedin.com/in/janedoe",
            order=1,
            photo=photo,
        )

        assert person.link_name == "LinkedIn"
        assert person.link_target == "https://linkedin.com/in/janedoe"
        assert person.order == 1
        assert person.has_link

    def test_ordering_by_order_then_name(self) -> None:
        """Test that ordering works correctly."""
        # Create people with different orders and names
        photo = self.create_test_image()

        person3 = self.model_class.objects.create(
            full_name="Charlie",
            title="Title",
            description="Desc",
            order=3,
            photo=photo,
        )
        person1 = self.model_class.objects.create(
            full_name="Alice",
            title="Title",
            description="Desc",
            order=1,
            photo=photo,
        )
        person2 = self.model_class.objects.create(
            full_name="Bob",
            title="Title",
            description="Desc",
            order=2,
            photo=photo,
        )
        # People with no order should come after ordered ones
        person_z = self.model_class.objects.create(
            full_name="Zoe",
            title="Title",
            description="Desc",
            order=None,
            photo=photo,
        )
        person_a = self.model_class.objects.create(
            full_name="Adam",
            title="Title",
            description="Desc",
            order=None,
            photo=photo,
        )

        people = list(self.model_class.objects.all())

        # Check ordering
        assert people[0] == person1  # order=1
        assert people[1] == person2  # order=2
        assert people[2] == person3  # order=3
        assert people[3] == person_a  # order=None, name="Adam"
        assert people[4] == person_z  # order=None, name="Zoe"

    def test_str_representation(self) -> None:
        """Test string representation."""
        photo = self.create_test_image()
        person = self.model_class.objects.create(
            full_name="Test Person", title="Test Title", description="Test", photo=photo
        )

        assert str(person) == "Test Person"

    def test_has_link_property(self) -> None:
        """Test the has_link property."""
        photo = self.create_test_image()

        # Without link
        person1 = self.model_class.objects.create(
            full_name="No Link", title="Title", description="Desc", photo=photo
        )
        assert not person1.has_link

        # With link
        person2 = self.model_class.objects.create(
            full_name="Has Link",
            title="Title",
            description="Desc",
            link_target="https://example.com",
            photo=photo,
        )
        assert person2.has_link

    def test_photo_upload_path(self) -> None:
        """Test that photo upload path is correctly generated."""
        member = self.model_class.objects.create(
            full_name="Test Person", title="Test Title", description="Test Description"
        )

        # Mock file
        mock_file = self.create_test_image()
        member.photo = mock_file
        member.save()

        # Check that UUID was prepended to filename (storage behavior)
        filename = member.photo.name

        assert filename is not None
        assert re.search(r"^[a-f0-9]{32}_test_photo\.jpg$", filename)

    def test_photo_orientation_preserved(self) -> None:
        """Test that photo orientation is preserved during processing."""

        # Create a test image with specific dimensions (portrait)
        img = Image.new("RGB", (600, 800), color="red")

        # Create EXIF data with orientation tag
        # Orientation 6 means the image needs to be rotated 90 degrees clockwise
        exif_data = img.getexif()
        exif_data[274] = 6  # 274 is the orientation tag

        # Save to bytes with EXIF
        buffer = BytesIO()
        img.save(buffer, format="JPEG", exif=exif_data)
        buffer.seek(0)

        # Create member with the oriented image
        member = self.model_class.objects.create(
            full_name="Test Person", title="Test Title", description="Test Description"
        )

        member.photo = SimpleUploadedFile(
            "test_oriented.jpg", buffer.read(), content_type="image/jpeg"
        )
        member.save()

        # Open the processed image
        member.photo.seek(0)
        processed_img = Image.open(member.photo)

        # After processing with orientation 6, the dimensions should be swapped
        # The 600x800 portrait image should now be 800x600 landscape
        # (or in this case, a 200x200 square crop)
        assert processed_img.size == (200, 200), (
            f"Expected (200, 200), got {processed_img.size}"
        )

    def test_get_photo_url(self) -> None:
        """Test the get_photo_url method."""
        photo = self.create_test_image()
        person = self.model_class.objects.create(
            full_name="URL Test", title="Title", description="Desc", photo=photo
        )

        # Should return a URL
        url = person.get_photo_url()
        assert url is not None
        assert "/media/" in url

        # Test with no photo
        person.photo = None
        person.save()
        assert person.get_photo_url() is None


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class BoardMemberModelTests(PersonModelTestMixin, TestCase):
    """Tests for BoardMember model."""

    model_class = BoardMember

    def test_verbose_names(self) -> None:
        """Test model verbose names."""
        assert BoardMember._meta.verbose_name == "Board Member"  # noqa: SLF001
        assert BoardMember._meta.verbose_name_plural == "Board of Directors"  # noqa: SLF001


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TechnicalMemberModelTests(PersonModelTestMixin, TestCase):
    """Tests for TechnicalMember model."""

    model_class = TechnicalMember

    def test_verbose_names(self) -> None:
        """Test model verbose names."""
        assert TechnicalMember._meta.verbose_name == "Technical Committee Member"  # noqa: SLF001
        assert (
            TechnicalMember._meta.verbose_name_plural == "Technical Steering Committee"  # noqa: SLF001
        )


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ExplorerMemberModelTests(PersonModelTestMixin, TestCase):
    """Tests for ExplorerMember model."""

    model_class = ExplorerMember

    def test_verbose_names(self) -> None:
        """Test model verbose names."""
        assert ExplorerMember._meta.verbose_name == "Explorer Board Member"  # noqa: SLF001
        assert ExplorerMember._meta.verbose_name_plural == "Explorer Advisory Board"  # noqa: SLF001
