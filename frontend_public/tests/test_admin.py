# -*- coding: utf-8 -*-

from __future__ import annotations

import io
from typing import TYPE_CHECKING
from typing import Any

import pytest
from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status

from frontend_public.admin import BoardMemberAdmin
from frontend_public.admin import ExplorerMemberAdmin
from frontend_public.admin import PersonAdminBase
from frontend_public.admin import TechnicalMemberAdmin
from frontend_public.models import BoardMember
from frontend_public.models import ExplorerMember
from frontend_public.models import TechnicalMember

if TYPE_CHECKING:
    from typing import Any

    from django.test import Client

    from speleodb.users.models import User

    type PersonAbstract = BoardMember | TechnicalMember | ExplorerMember


def create_test_image() -> SimpleUploadedFile:
    """Create a test image file."""
    # Create a 1x1 red pixel PNG

    img = Image.new("RGB", (1, 1), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    return SimpleUploadedFile(
        name="test_photo.jpg", content=img_bytes.read(), content_type="image/jpeg"
    )


@pytest.fixture
def test_image() -> SimpleUploadedFile:
    """Fixture to create test image."""
    return create_test_image()


@pytest.fixture
def board_member(db: None, test_image: SimpleUploadedFile) -> BoardMember:
    """Create a test board member."""
    return BoardMember.objects.create(
        full_name="Test Board Member",
        title="Board Title",
        description="Board description",
        photo=test_image,
    )


@pytest.fixture
def technical_member(db: None, test_image: SimpleUploadedFile) -> TechnicalMember:
    """Create a test technical member."""
    return TechnicalMember.objects.create(
        full_name="Test Technical Member",
        title="Technical Title",
        description="Technical description",
        photo=test_image,
    )


@pytest.fixture
def explorer_member(db: None, test_image: SimpleUploadedFile) -> ExplorerMember:
    """Create a test explorer member."""
    return ExplorerMember.objects.create(
        full_name="Test Explorer Member",
        title="Explorer Title",
        description="Explorer description",
        photo=test_image,
    )


class PersonAdminTestMixin:
    """Base test mixin for person admin tests."""

    model_class: type[PersonAbstract]
    admin_class: type[PersonAdminBase]

    def get_model_name(self) -> str:
        """Get the model name for URL construction."""
        return self.model_class.__name__.lower()

    def create_person(
        self, test_image: SimpleUploadedFile, **kwargs: Any
    ) -> PersonAbstract:
        """Create a person instance."""
        defaults = {
            "full_name": "Test Person",
            "title": "Test Title",
            "description": "Test Description",
            "photo": test_image,
        }
        defaults.update(kwargs)
        return self.model_class.objects.create(**defaults)

    def test_admin_list_display(self, db: None) -> None:
        """Test list display configuration."""
        site = AdminSite()
        admin = self.admin_class(self.model_class, site)

        expected_fields = [
            "photo_preview",
            "full_name",
            "title",
            "order",
            "has_link",
            "created_at",
        ]

        assert admin.list_display == expected_fields

    def test_admin_list_editable_order(self, db: None) -> None:
        """Test that order field is editable in list view."""
        site = AdminSite()
        admin = self.admin_class(self.model_class, site)

        assert "order" in admin.list_editable

    def test_photo_preview_rendering(
        self, db: None, test_image: SimpleUploadedFile
    ) -> None:
        """Test photo preview HTML generation."""
        site = AdminSite()
        admin = self.admin_class(self.model_class, site)

        person = self.create_person(test_image)

        # Test with photo
        html = admin.photo_preview(person)
        assert "<img" in html
        assert 'style="width: 50px; height: 50px;' in html
        assert "object-fit: cover" in html
        assert "border-radius: 50%" in html

        # Test without photo
        person.photo = None
        html = admin.photo_preview(person)
        assert html == "-"

    def test_photo_preview_large_rendering(
        self, db: None, test_image: SimpleUploadedFile
    ) -> None:
        """Test large photo preview HTML generation."""
        site = AdminSite()
        admin = self.admin_class(self.model_class, site)

        person = self.create_person(test_image)

        # Test with photo
        html = admin.photo_preview_large(person)
        assert "<img" in html
        assert 'style="max-width: 300px; max-height: 300px;' in html
        assert "object-fit: contain" in html

        # Test without photo
        person.photo = None
        html = admin.photo_preview_large(person)
        assert html == "No photo uploaded"

    def test_has_link_display(self, db: None) -> None:
        """Test has_link display method."""
        site = AdminSite()
        admin = self.admin_class(self.model_class, site)

        # Create person with link
        person_with_link = self.create_person(
            test_image=create_test_image(),
            link_name="LinkedIn",
            link_target="https://linkedin.com/test",
        )

        # Create person without link
        person_without_link = self.create_person(test_image=create_test_image())

        assert admin.has_link(person_with_link) == "✓"
        assert admin.has_link(person_without_link) == "-"

    def test_admin_fieldsets(self, db: None) -> None:
        """Test fieldset configuration."""
        site = AdminSite()
        admin = self.admin_class(self.model_class, site)

        # Check fieldsets structure
        assert len(admin.fieldsets) == 5  # noqa: PLR2004  # pyright: ignore[reportArgumentType]

        # Check main fields
        assert admin.fieldsets[0][0] is None  # pyright: ignore[reportOptionalSubscript]
        assert "full_name" in admin.fieldsets[0][1]["fields"]  # pyright: ignore[reportOptionalSubscript]
        assert "title" in admin.fieldsets[0][1]["fields"]  # pyright: ignore[reportOptionalSubscript]
        assert "order" in admin.fieldsets[0][1]["fields"]  # pyright: ignore[reportOptionalSubscript]

        # Check details section
        assert admin.fieldsets[1][0] == "Details"  # pyright: ignore[reportOptionalSubscript]
        assert "description" in admin.fieldsets[1][1]["fields"]  # pyright: ignore[reportOptionalSubscript]

        # Check link section
        assert admin.fieldsets[2][0] == "Link Information"  # pyright: ignore[reportOptionalSubscript]
        assert "collapse" in admin.fieldsets[2][1]["classes"]  # pyright: ignore[reportOptionalSubscript,reportTypedDictNotRequiredAccess]

    def test_admin_search_fields(self, db: None) -> None:
        """Test search field configuration."""
        site = AdminSite()
        admin = self.admin_class(self.model_class, site)

        expected_search_fields = ["full_name", "title", "description"]
        assert admin.search_fields == expected_search_fields

    def test_admin_list_filter(self, db: None) -> None:
        """Test list filter configuration."""
        site = AdminSite()
        admin = self.admin_class(self.model_class, site)

        expected_filters = ["created_at", "updated_at"]
        assert admin.list_filter == expected_filters

    def test_admin_readonly_fields(self, db: None) -> None:
        """Test readonly fields."""
        site = AdminSite()
        admin = self.admin_class(self.model_class, site)

        expected_readonly = ["id", "created_at", "updated_at", "photo_preview_large"]
        assert admin.readonly_fields == expected_readonly


class TestBoardMemberAdmin(PersonAdminTestMixin):
    """Tests for BoardMemberAdmin."""

    model_class = BoardMember
    admin_class = BoardMemberAdmin

    @pytest.mark.filterwarnings(
        "ignore:.*FORMS_URLFIELD_ASSUME_HTTPS.*:django.utils.deprecation.RemovedInDjango60Warning"
    )
    def test_admin_registration(
        self, client: Client, admin_user: User, db: None
    ) -> None:
        """Test that BoardMember is registered in admin."""
        client.force_login(admin_user)
        url = reverse("admin:frontend_public_boardmember_changelist")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "Board of Directors" in response.content.decode()


class TestTechnicalMemberAdmin(PersonAdminTestMixin):
    """Tests for TechnicalMemberAdmin."""

    model_class = TechnicalMember
    admin_class = TechnicalMemberAdmin

    @pytest.mark.filterwarnings(
        "ignore:.*FORMS_URLFIELD_ASSUME_HTTPS.*:django.utils.deprecation.RemovedInDjango60Warning"
    )
    def test_admin_registration(
        self, client: Client, admin_user: User, db: None
    ) -> None:
        """Test that TechnicalMember is registered in admin."""
        client.force_login(admin_user)
        url = reverse("admin:frontend_public_technicalmember_changelist")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "Technical Steering Committee" in response.content.decode()


class TestExplorerMemberAdmin(PersonAdminTestMixin):
    """Tests for ExplorerMemberAdmin."""

    model_class = ExplorerMember
    admin_class = ExplorerMemberAdmin

    @pytest.mark.filterwarnings(
        "ignore::django.utils.deprecation.RemovedInDjango60Warning"
    )
    def test_admin_registration(
        self, client: Client, admin_user: User, db: None
    ) -> None:
        """Test that ExplorerMember is registered in admin."""
        client.force_login(admin_user)
        url = reverse("admin:frontend_public_explorermember_changelist")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "Explorer Advisory Board" in response.content.decode()
