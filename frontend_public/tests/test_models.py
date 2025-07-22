# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import tempfile
from typing import TYPE_CHECKING

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings

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
        # Create a minimal valid JPEG file
        content = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n"
            b"\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d"
            b"\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b"
            b"\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05"
            b"\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03"
            b"\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03"
            b"\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05"
            b'\x12!1A\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0'
            b"$3br\x82\t\n\x16\x17\x18\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefg"
            b"hijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97"
            b"\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6"
            b"\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5"
            b"\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2"
            b"\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00?"
            b"\x00\xfb\xd3N\xe1\x18\xd2M\xca)%\x00\xff\xd9"
        )
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
        assert person.created_at is not None
        assert person.updated_at is not None

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
        """Test that photos are uploaded to the correct path."""
        photo = self.create_test_image()
        person = self.model_class.objects.create(
            full_name="Photo Test", title="Title", description="Desc", photo=photo
        )

        # Photo should have a unique filename with UUID prefix
        assert person.photo.name
        # Check that UUID was prepended
        assert re.search(r"^[a-f0-9]{32}_test_photo\.jpg$", person.photo.name)

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
