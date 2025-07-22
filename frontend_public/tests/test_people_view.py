# -*- coding: utf-8 -*-
"""Tests for the people page view."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status

from frontend_public.models import BoardMember
from frontend_public.models import ExplorerMember
from frontend_public.models import TechnicalMember

if TYPE_CHECKING:
    from django.test import Client


def create_test_image() -> SimpleUploadedFile:
    """Create a test image file."""
    # Create a simple 1x1 red pixel image
    img = Image.new("RGB", (1, 1), color="red")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    return SimpleUploadedFile(
        name="test_photo.jpg", content=img_bytes.read(), content_type="image/jpeg"
    )


@pytest.mark.django_db
class TestPeoplePageView:
    """Test the people page view."""

    def test_people_page_loads(self, client: Client) -> None:
        """Test that the people page loads successfully."""
        url = reverse("people")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "Meet Our Community" in response.content.decode()

    def test_empty_people_page(self, client: Client) -> None:
        """Test that the page works when there are no people."""
        url = reverse("people")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        # Sections should not appear when empty
        assert "Board of Directors" not in response.content.decode()
        assert "Technical Steering Committee" not in response.content.decode()
        assert "Explorer Advisory Board" not in response.content.decode()

    def test_board_members_display(self, client: Client, db: None) -> None:
        """Test that board members are displayed correctly."""
        # Create test board members
        _ = BoardMember.objects.create(
            full_name="John Doe",
            title="Board Chair",
            description="Test description for John",
            order=1,
            photo=create_test_image(),
        )
        _ = BoardMember.objects.create(
            full_name="Jane Smith",
            title="Treasurer",
            description="Test description for Jane",
            order=2,
            link_name="LinkedIn",
            link_target="https://linkedin.com/jane",
            photo=create_test_image(),
        )

        url = reverse("people")
        response = client.get(url)
        content = response.content.decode()

        assert response.status_code == status.HTTP_200_OK
        assert "Board of Directors" in content
        assert "John Doe" in content
        assert "Board Chair" in content
        assert "Test description for John" in content
        assert "Jane Smith" in content
        assert "Treasurer" in content
        assert "Test description for Jane" in content
        assert "LinkedIn" in content
        assert "https://linkedin.com/jane" in content

    def test_technical_members_display(self, client: Client, db: None) -> None:
        """Test that technical members are displayed correctly."""
        # Create test technical members
        _ = TechnicalMember.objects.create(
            full_name="Alice Johnson",
            title="Lead Architect",
            description="Test description for Alice",
            photo=create_test_image(),
        )

        url = reverse("people")
        response = client.get(url)
        content = response.content.decode()

        assert response.status_code == status.HTTP_200_OK
        assert "Technical Steering Committee" in content
        assert "Alice Johnson" in content
        assert "Lead Architect" in content
        assert "Test description for Alice" in content

    def test_explorer_members_display(self, client: Client, db: None) -> None:
        """Test that explorer members are displayed correctly."""
        # Create test explorer members
        _ = ExplorerMember.objects.create(
            full_name="Bob Wilson",
            title="Cave Diving Pioneer",
            description="Test description for Bob",
            photo=create_test_image(),
        )

        url = reverse("people")
        response = client.get(url)
        content = response.content.decode()

        assert response.status_code == status.HTTP_200_OK
        assert "Explorer Advisory Board" in content
        assert "Bob Wilson" in content
        assert "Cave Diving Pioneer" in content
        assert "Test description for Bob" in content

    def test_ordering_by_order_field(self, client: Client, db: None) -> None:
        """Test that people are ordered correctly."""
        # Create members with different orders
        BoardMember.objects.create(
            full_name="Third Person",
            title="Member",
            description="Description",
            order=3,
            photo=create_test_image(),
        )
        BoardMember.objects.create(
            full_name="First Person",
            title="Chair",
            description="Description",
            order=1,
            photo=create_test_image(),
        )
        BoardMember.objects.create(
            full_name="Second Person",
            title="Secretary",
            description="Description",
            order=2,
            photo=create_test_image(),
        )

        url = reverse("people")
        response = client.get(url)
        content = response.content.decode()

        # Check that people appear in the correct order
        first_pos = content.find("First Person")
        second_pos = content.find("Second Person")
        third_pos = content.find("Third Person")

        assert first_pos < second_pos < third_pos

    def test_member_without_photo(self, client: Client, db: None) -> None:
        """Test that members without photos show initials."""
        # Create member without photo
        _ = BoardMember.objects.create(
            full_name="No Photo Person",
            title="Member",
            description="Description",
            order=1,
        )

        url = reverse("people")
        response = client.get(url)
        content = response.content.decode()

        assert response.status_code == status.HTTP_200_OK
        assert "No Photo Person" in content
        # Should show first initial
        assert ">N<" in content  # The initial is displayed in a span

    def test_grid_layout_classes(self, client: Client, db: None) -> None:
        """Test that grid layout classes are applied correctly."""
        # Create exactly 3 technical members (should use 3 columns)
        for i in range(3):
            TechnicalMember.objects.create(
                full_name=f"Tech Member {i + 1}",
                title="Developer",
                description="Description",
                photo=create_test_image(),
            )

        url = reverse("people")
        response = client.get(url)
        content = response.content.decode()

        assert response.status_code == status.HTTP_200_OK
        # Should have 3-column grid class
        assert "lg:grid-cols-3" in content

    def test_all_sections_together(self, client: Client, db: None) -> None:
        """Test page with all three types of members."""
        # Create one of each type
        BoardMember.objects.create(
            full_name="Board Member",
            title="Chair",
            description="Board description",
            photo=create_test_image(),
        )
        TechnicalMember.objects.create(
            full_name="Tech Member",
            title="Developer",
            description="Tech description",
            photo=create_test_image(),
        )
        ExplorerMember.objects.create(
            full_name="Explorer Member",
            title="Pioneer",
            description="Explorer description",
            photo=create_test_image(),
        )

        url = reverse("people")
        response = client.get(url)
        content = response.content.decode()

        assert response.status_code == status.HTTP_200_OK
        assert "Board of Directors" in content
        assert "Technical Steering Committee" in content
        assert "Explorer Advisory Board" in content
        assert "Board Member" in content
        assert "Tech Member" in content
        assert "Explorer Member" in content
