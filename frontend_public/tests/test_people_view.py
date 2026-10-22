# -*- coding: utf-8 -*-
"""Tests for the people page view."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from rest_framework import status

from frontend_public.models import BoardMember
from frontend_public.models import ExplorerMember
from frontend_public.models import ScientificMember
from frontend_public.models import TechnicalMember

if TYPE_CHECKING:
    from django.test import Client


@pytest.mark.django_db
class TestPeoplePageView:
    """Test the people page view."""

    def test_empty_people_page(self, client: Client) -> None:
        """Test that the page works when there are no people."""
        url = reverse("people")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        # Sections should not appear when empty
        assert "Board of Directors" not in response.content.decode()
        assert "Technical Steering Committee" not in response.content.decode()
        assert "Explorer Advisory Board" not in response.content.decode()
        assert "Scientific Advisory Board" not in response.content.decode()

    def test_board_members_display(self, client: Client, db: None) -> None:
        """Test that board members are displayed correctly."""
        # Create test board members
        # Stored names exercise rendering; photo processing has its own model tests.
        BoardMember.objects.bulk_create(
            [
                BoardMember(
                    full_name="John Doe",
                    title="Board Chair",
                    description="Test description for John",
                    order=1,
                    photo="test_photo.jpg",
                ),
                BoardMember(
                    full_name="Jane Smith",
                    title="Treasurer",
                    description="Test description for Jane",
                    order=2,
                    link_name="LinkedIn",
                    link_target="https://linkedin.com/jane",
                    photo="test_photo.jpg",
                ),
            ]
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
        assert "test_photo.jpg" in content

    def test_ordering_by_order_field(self, client: Client, db: None) -> None:
        """Test that people are ordered correctly."""
        # Create members with different orders
        BoardMember.objects.create(
            full_name="Third Person",
            title="Member",
            description="Description",
            order=3,
        )
        BoardMember.objects.create(
            full_name="First Person",
            title="Chair",
            description="Description",
            order=1,
        )
        BoardMember.objects.create(
            full_name="Second Person",
            title="Secretary",
            description="Description",
            order=2,
        )

        url = reverse("people")
        response = client.get(url)
        content = response.content.decode()

        # Check that people appear in the correct order
        first_pos = content.find("First Person")
        second_pos = content.find("Second Person")
        third_pos = content.find("Third Person")

        assert 0 <= first_pos < second_pos < third_pos

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

    def test_all_sections_together(self, client: Client, db: None) -> None:
        """Test page with all four types of members."""
        # Create one of each type
        BoardMember.objects.create(
            full_name="Board Member",
            title="Chair",
            description="Board description",
        )
        TechnicalMember.objects.create(
            full_name="Tech Member",
            title="Developer",
            description="Tech description",
        )
        ExplorerMember.objects.create(
            full_name="Explorer Member",
            title="Pioneer",
            description="Explorer description",
        )

        ScientificMember.objects.create(
            full_name="Scientific Member",
            title="Researcher",
            description="Scientific description",
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
        assert "Developer" in content
        assert "Tech description" in content
        assert "Pioneer" in content
        assert "Explorer description" in content
        assert "Scientific Advisory Board" in content
        assert "Scientific Member" in content
        assert "Researcher" in content
        assert "Scientific description" in content
