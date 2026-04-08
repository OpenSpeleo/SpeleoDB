# -*- coding: utf-8 -*-

from __future__ import annotations

import re

from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.users.tests.factories import UserFactory

EXPECTED_COLUMN_COUNT = 10


class TestProjectsTableLayout(TestCase):
    """
    Regression tests for the projects listing page HTML structure.

    These tests guard against:
    - Column widths shifting when country groups are expanded/collapsed
    - Container-level scrollbar reappearing on the table wrapper
    - Sticky table header losing its offset below the site header
    - FOUC (flash of expanded groups before collapse restoration)
    """

    def setUp(self) -> None:
        super().setUp()
        self.user = UserFactory.create()
        self.project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project,
            level=PermissionLevel.ADMIN,
        )
        self.client.force_login(self.user)
        url = reverse("private:projects")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        self.html = response.content.decode()

    def test_table_wrapper_has_no_overflow_constraint(self) -> None:
        """The table wrapper must not constrain height or add its own scrollbar."""
        table_tag = re.search(r'<table\s[^>]*class="table-fixed[^"]*"', self.html)
        assert table_tag is not None

        start = table_tag.start()
        preceding_500 = self.html[max(0, start - 500) : start]

        assert "overflow-auto" not in preceding_500
        assert "max-h-" not in preceding_500

    def test_thead_sticky_below_site_header(self) -> None:
        """The thead must stick below the site header (top-16), not at top-0."""
        thead_match = re.search(r"<thead\s[^>]*class=\"([^\"]+)\"", self.html)
        assert thead_match is not None

        classes = thead_match.group(1)
        assert "sticky" in classes
        assert "top-16" in classes
        assert "top-0" not in classes

    def test_table_uses_fixed_layout(self) -> None:
        """The table must use table-fixed so column widths don't shift
        when country groups are expanded/collapsed."""
        table_match = re.search(r"<table\s[^>]*class=\"([^\"]+)\"", self.html)
        assert table_match is not None

        classes = table_match.group(1)
        assert "table-fixed" in classes
        assert "table-auto" not in classes

    def test_all_columns_have_explicit_widths(self) -> None:
        """Every <th> in the table-fixed header must have a w-[…%] class
        so widths stay stable regardless of visible content."""
        thead_match = re.search(r"<thead[^>]*>.*?</thead>", self.html, re.DOTALL)
        assert thead_match is not None

        th_classes = re.findall(r"<th\s[^>]*class=\"([^\"]+)\"", thead_match.group())
        assert len(th_classes) == EXPECTED_COLUMN_COUNT

        width_pattern = re.compile(r"w-\[\d+%\]")
        for idx, classes in enumerate(th_classes):
            assert width_pattern.search(classes), (
                f"<th> at index {idx} is missing a w-[…%] class: {classes}"
            )

    def test_column_widths_sum_to_100(self) -> None:
        """Column percentage widths must sum to 100%."""
        thead_match = re.search(r"<thead[^>]*>.*?</thead>", self.html, re.DOTALL)
        assert thead_match is not None

        percentages = re.findall(r"w-\[(\d+)%\]", thead_match.group())
        assert len(percentages) == EXPECTED_COLUMN_COUNT

        total = sum(int(p) for p in percentages)
        assert total == 100, f"Column widths sum to {total}%, expected 100%"  # noqa: PLR2004

    def test_collapse_restoration_before_document_ready(self) -> None:
        """Collapse state must be restored via a synchronous inline <script>
        placed after the .country-group elements and before $(document).ready()
        to prevent FOUC (flash of uncollapsed content)."""
        sync_script_pattern = re.compile(
            r"<script>\s*\n?"
            r".*speleo_projects_collapsed_countries.*"
            r"classList\.add\(['\"]collapsed['\"]\)",
            re.DOTALL,
        )
        sync_match = sync_script_pattern.search(self.html)
        assert sync_match is not None, (
            "Synchronous collapse-restoration <script> not found"
        )

        doc_ready_pos = self.html.find("$( document ).ready(")
        if doc_ready_pos == -1:
            doc_ready_pos = self.html.find("$(document).ready(")
        assert doc_ready_pos != -1

        assert sync_match.start() < doc_ready_pos, (
            "Collapse restoration script must appear before $(document).ready()"
        )

    # ------------------------------------------------------------------ #
    # Responsive column hiding
    # ------------------------------------------------------------------ #

    def _extract_breakpoint_block(self, max_width: int) -> str:
        """Return the CSS inside ``@media (max-width: <max_width>px) { … }``,
        correctly handling nested braces."""
        marker = f"max-width: {max_width}px"
        start = self.html.find(marker)
        assert start != -1, f"@media ({marker}) block not found"

        open_brace = self.html.index("{", start)
        depth = 1
        pos = open_brace + 1
        while depth > 0 and pos < len(self.html):
            if self.html[pos] == "{":
                depth += 1
            elif self.html[pos] == "}":
                depth -= 1
            pos += 1
        return self.html[open_brace + 1 : pos - 1]

    def _assert_column_hidden(self, css_block: str, nth: int) -> None:
        """Assert that both th and td nth-child(nth) are display:none."""
        hide_re = re.compile(rf"th:nth-child\({nth}\).*?display:\s*none", re.DOTALL)
        assert hide_re.search(css_block), f"Column {nth} (th) not hidden in CSS block"
        hide_td_re = re.compile(rf"td:nth-child\({nth}\).*?display:\s*none", re.DOTALL)
        assert hide_td_re.search(css_block), (
            f"Column {nth} (td) not hidden in CSS block"
        )

    def _extract_widths(self, css_block: str) -> dict[int, int]:
        """Return {nth: pct} for all ``th:nth-child(N) { width: X% }``."""
        return {
            int(m.group(1)): int(m.group(2))
            for m in re.finditer(
                r"th:nth-child\((\d+)\)\s*\{\s*width:\s*(\d+)%", css_block
            )
        }

    def test_responsive_hide_collaborators_and_editing_since_below_1700(self) -> None:
        """Collaborators (col 3) and Editing Since (col 9) hidden below 1700px,
        widths sum to 100%."""
        block = self._extract_breakpoint_block(1699)
        self._assert_column_hidden(block, 3)
        self._assert_column_hidden(block, 9)

        widths = self._extract_widths(block)
        assert 3 not in widths, "Hidden column 3 should not have a width override"  # noqa: PLR2004
        assert 9 not in widths, "Hidden column 9 should not have a width override"  # noqa: PLR2004
        assert sum(widths.values()) == 100, (  # noqa: PLR2004
            f"Visible widths sum to {sum(widths.values())}%, expected 100%"
        )

    def test_responsive_hide_revisions_below_1500(self) -> None:
        """Revisions (col 4) also hidden below 1500px, widths sum to 100%."""
        block = self._extract_breakpoint_block(1499)
        self._assert_column_hidden(block, 4)

        widths = self._extract_widths(block)
        assert 4 not in widths, "Hidden column 4 should not have a width override"  # noqa: PLR2004
        assert sum(widths.values()) == 100, (  # noqa: PLR2004
            f"Visible widths sum to {sum(widths.values())}%, expected 100%"
        )

    def test_responsive_hide_editor_below_1450(self) -> None:
        """Current Editor (col 8) also hidden below 1450px, widths sum to 100%."""
        block = self._extract_breakpoint_block(1449)
        self._assert_column_hidden(block, 8)

        widths = self._extract_widths(block)
        assert 8 not in widths, "Hidden column 8 should not have a width override"  # noqa: PLR2004
        assert sum(widths.values()) == 100, (  # noqa: PLR2004
            f"Visible widths sum to {sum(widths.values())}%, expected 100%"
        )

    def test_responsive_hide_last_edit_below_1300(self) -> None:
        """Last Edit (col 7) also hidden below 1300px, widths sum to 100%."""
        block = self._extract_breakpoint_block(1299)
        self._assert_column_hidden(block, 7)

        widths = self._extract_widths(block)
        assert 7 not in widths, "Hidden column 7 should not have a width override"  # noqa: PLR2004
        assert sum(widths.values()) == 100, (  # noqa: PLR2004
            f"Visible widths sum to {sum(widths.values())}%, expected 100%"
        )
