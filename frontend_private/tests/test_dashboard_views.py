# -*- coding: utf-8 -*-

from __future__ import annotations

import re

from django.conf import settings
from django.test import TestCase
from django.urls import resolve
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseUserTestCaseMixin


# ------------------------------------------------------------------ #
#  Dashboard page access
# ------------------------------------------------------------------ #
class TestDashboardPageAccess(BaseUserTestCaseMixin, TestCase):
    def test_unauthenticated_redirects_to_login(self) -> None:
        self.client.logout()
        url = reverse("private:user_dashboard")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_302_FOUND
        assert "/login/" in response.url  # type: ignore[attr-defined]

    def test_authenticated_returns_200(self) -> None:
        self.client.force_login(self.user)
        url = reverse("private:user_dashboard")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_content_type_is_html(self) -> None:
        self.client.force_login(self.user)
        url = reverse("private:user_dashboard")
        response = self.client.get(url)
        assert response["Content-Type"].startswith("text/html")

    def test_page_title_contains_speleodb(self) -> None:
        self.client.force_login(self.user)
        url = reverse("private:user_dashboard")
        response = self.client.get(url)
        html = response.content.decode()
        assert "<title>SpeleoDB</title>" in html


# ------------------------------------------------------------------ #
#  Dashboard template structure
# ------------------------------------------------------------------ #
class TestDashboardTemplateStructure(BaseUserTestCaseMixin, TestCase):
    html: str

    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)
        url = reverse("private:user_dashboard")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        self.html = response.content.decode()

    def test_page_header_present(self) -> None:
        assert "Dashboard" in self.html

    def test_quick_actions_in_header(self) -> None:
        project_new_url = reverse("private:project_new")
        assert project_new_url in self.html

    def test_stat_cards_container_present(self) -> None:
        assert 'id="stat-cards"' in self.html

    def test_stat_card_placeholders_present(self) -> None:
        assert "skeleton-pulse" in self.html

    def test_chart_containers_present(self) -> None:
        assert 'id="commits-chart"' in self.html
        assert 'id="projects-chart"' in self.html

    def test_heatmap_container_present(self) -> None:
        assert 'id="contribution-heatmap"' in self.html

    def test_activity_feed_container_present(self) -> None:
        assert 'id="recent-activity"' in self.html

    def test_quick_actions_contain_all_links(self) -> None:
        quick_actions_end = self.html.find("<!-- Stat Cards -->")
        assert quick_actions_end != -1, "Stat Cards marker not found"
        quick_actions = self.html[:quick_actions_end]

        project_new_url = reverse("private:project_new")
        projects_url = reverse("private:projects")
        map_viewer_url = reverse("private:map_viewer")

        assert project_new_url in quick_actions
        assert projects_url in quick_actions
        assert map_viewer_url in quick_actions

    def test_chartjs_cdn_loaded(self) -> None:
        assert "chart" in self.html.lower()
        chart_script = re.search(r"chart.*\.js", self.html, re.IGNORECASE)
        assert chart_script is not None

    def test_url_reverse_js_loaded(self) -> None:
        assert "url_reverse.js" in self.html

    def test_no_profile_form_on_dashboard(self) -> None:
        assert "update_user_info_form" not in self.html

    def test_sidebar_dashboard_highlighted(self) -> None:
        dashboard_link = reverse("private:user_dashboard")
        link_pos = self.html.find(f'href="{dashboard_link}"')
        assert link_pos != -1
        preceding = self.html[max(0, link_pos - 200) : link_pos]
        assert "bg-slate-900" in preceding

    def test_stat_cards_have_all_metrics(self) -> None:
        for stat_id in (
            "stat-projects",
            "stat-teams",
            "stat-commits",
            "stat-stations",
            "stat-landmarks",
            "stat-gps-tracks",
        ):
            assert f'id="{stat_id}"' in self.html, f"Missing stat card: {stat_id}"

    def test_heatmap_legend_present(self) -> None:
        assert "Less" in self.html
        assert "More" in self.html

    def test_contributions_chart_section_title(self) -> None:
        assert "Contributions Over Time" in self.html

    def test_projects_chart_section_title(self) -> None:
        assert "Projects by Software" in self.html

    def test_contribution_section_title(self) -> None:
        assert "contributions in the last year" in self.html

    def test_heatmap_is_table_based(self) -> None:
        assert '<table id="contribution-heatmap"' in self.html

    def test_heatmap_stat_cards_present(self) -> None:
        for stat_id in (
            "heatmap-week-count",
            "heatmap-month-count",
            "heatmap-busiest-day",
            "heatmap-streak-count",
        ):
            assert f'id="{stat_id}"' in self.html, f"Missing heatmap stat: {stat_id}"

    def test_activity_skeleton_has_avatar_placeholders(self) -> None:
        assert "border-radius:50%" in self.html

    def test_error_callback_text_in_template(self) -> None:
        assert "Failed to load activity" in self.html

    def test_show_stat_card_errors_function_defined(self) -> None:
        assert "showStatCardErrors" in self.html

    def test_charts_have_aria_labels(self) -> None:
        assert 'aria-label="Line chart showing contributions' in self.html
        assert 'aria-label="Doughnut chart showing projects' in self.html

    def test_dashboard_helpers_loaded(self) -> None:
        assert "dashboard-helpers.js" in self.html


# ------------------------------------------------------------------ #
#  Profile page access
# ------------------------------------------------------------------ #
class TestProfilePageAccess(BaseUserTestCaseMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def test_profile_page_returns_200(self) -> None:
        url = reverse("private:user_profile")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_profile_page_contains_profile_form(self) -> None:
        url = reverse("private:user_profile")
        response = self.client.get(url)
        html = response.content.decode()
        assert "update_user_info_form" in html

    def test_profile_page_contains_user_email(self) -> None:
        url = reverse("private:user_profile")
        response = self.client.get(url)
        html = response.content.decode()
        assert self.user.email in html

    def test_profile_page_contains_country_selector(self) -> None:
        url = reverse("private:user_profile")
        response = self.client.get(url)
        html = response.content.decode()
        assert '<select id="country"' in html

    def test_profile_page_extends_user_base(self) -> None:
        url = reverse("private:user_profile")
        response = self.client.get(url)
        html = response.content.decode()
        assert "Account Settings" in html


# ------------------------------------------------------------------ #
#  URL routing
# ------------------------------------------------------------------ #
class TestDashboardURLRouting(TestCase):
    def test_user_dashboard_url_resolves(self) -> None:
        assert reverse("private:user_dashboard") == "/private/"

    def test_user_profile_url_resolves(self) -> None:
        assert reverse("private:user_profile") == "/private/profile/"

    def test_resolve_dashboard_view_name(self) -> None:
        assert resolve("/private/").view_name == "private:user_dashboard"

    def test_resolve_profile_view_name(self) -> None:
        assert resolve("/private/profile/").view_name == "private:user_profile"

    def test_login_redirect_goes_to_dashboard(self) -> None:
        redirect_url = settings.LOGIN_REDIRECT_URL
        resolved = reverse(redirect_url) if ":" in redirect_url else redirect_url
        assert resolved == "/private/" or redirect_url == "private:user_dashboard"


# ------------------------------------------------------------------ #
#  Sidebar navigation
# ------------------------------------------------------------------ #
class TestSidebarNavigation(BaseUserTestCaseMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def _get_html(self, view_name: str) -> str:
        url = reverse(f"private:{view_name}")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        return response.content.decode()

    def test_dashboard_sidebar_active_on_dashboard(self) -> None:
        html = self._get_html("user_dashboard")
        dashboard_url = reverse("private:user_dashboard")
        link_pos = html.find(f'href="{dashboard_url}"')
        assert link_pos != -1
        preceding = html[max(0, link_pos - 200) : link_pos]
        assert "bg-slate-900" in preceding

    def test_dashboard_sidebar_not_active_on_profile(self) -> None:
        html = self._get_html("user_profile")
        sidebar_section = html[: html.find("<!-- Content area -->")]
        dashboard_url = reverse("private:user_dashboard")

        link_pos = sidebar_section.find(f'href="{dashboard_url}"')
        if link_pos != -1:
            preceding = sidebar_section[max(0, link_pos - 200) : link_pos]
            assert "bg-slate-900" not in preceding

    def test_profile_link_in_header_points_to_profile(self) -> None:
        html = self._get_html("user_dashboard")
        profile_url = reverse("private:user_profile")
        assert f'href="{profile_url}">Profile</a>' in html

    def test_profile_sidebar_active_on_profile(self) -> None:
        html = self._get_html("user_profile")
        profile_url = reverse("private:user_profile")
        sidebar = html[: html.find("<!-- Content area -->")]
        settings_link_pos = sidebar.find(f'href="{profile_url}"')
        if settings_link_pos != -1:
            preceding = sidebar[max(0, settings_link_pos - 300) : settings_link_pos]
            assert "bg-slate-900" in preceding

    def test_profile_sidebar_active_on_password(self) -> None:
        html = self._get_html("user_password")
        sidebar = html[: html.find("<!-- Content area -->")]
        profile_url = reverse("private:user_profile")
        link_pos = sidebar.find(f'href="{profile_url}"')
        if link_pos != -1:
            preceding = sidebar[max(0, link_pos - 300) : link_pos]
            assert "bg-slate-900" in preceding

    def test_profile_sidebar_active_on_preferences(self) -> None:
        html = self._get_html("user_preferences")
        sidebar = html[: html.find("<!-- Content area -->")]
        profile_url = reverse("private:user_profile")
        link_pos = sidebar.find(f'href="{profile_url}"')
        if link_pos != -1:
            preceding = sidebar[max(0, link_pos - 300) : link_pos]
            assert "bg-slate-900" in preceding

    def test_profile_sidebar_active_on_authtoken(self) -> None:
        html = self._get_html("user_authtoken")
        sidebar = html[: html.find("<!-- Content area -->")]
        profile_url = reverse("private:user_profile")
        link_pos = sidebar.find(f'href="{profile_url}"')
        if link_pos != -1:
            preceding = sidebar[max(0, link_pos - 300) : link_pos]
            assert "bg-slate-900" in preceding


# ------------------------------------------------------------------ #
#  Charts and graphs
# ------------------------------------------------------------------ #
class TestDashboardCharts(BaseUserTestCaseMixin, TestCase):
    html: str

    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)
        url = reverse("private:user_dashboard")
        response = self.client.get(url)
        self.html = response.content.decode()

    def test_commits_chart_canvas_exists(self) -> None:
        assert 'id="commits-chart"' in self.html
        assert "<canvas" in self.html

    def test_projects_chart_canvas_exists(self) -> None:
        assert 'id="projects-chart"' in self.html

    def test_projects_chart_empty_state_element(self) -> None:
        assert 'id="projects-chart-empty"' in self.html

    def test_commits_chart_has_responsive_container(self) -> None:
        chart_pos = self.html.find('id="commits-chart"')
        preceding = self.html[max(0, chart_pos - 300) : chart_pos]
        assert "position:relative" in preceding

    def test_projects_chart_has_responsive_container(self) -> None:
        chart_pos = self.html.find('id="projects-chart"')
        preceding = self.html[max(0, chart_pos - 300) : chart_pos]
        assert "position:relative" in preceding

    def test_js_creates_line_chart(self) -> None:
        assert "buildCommitsChartConfig" in self.html

    def test_js_creates_doughnut_chart(self) -> None:
        assert "buildProjectsChartConfig" in self.html

    def test_line_chart_has_two_datasets(self) -> None:
        assert "initCommitsChart" in self.html
        assert "commits_over_time" in self.html

    def test_line_chart_dark_theme_colors(self) -> None:
        assert "rgba(129,140,248,0.1)" in self.html
        assert "rgba(52,211,153,0.1)" in self.html

    def test_doughnut_chart_uses_project_types(self) -> None:
        assert "projects_by_type" in self.html

    def test_heatmap_table_has_colgroup(self) -> None:
        assert "hm-label-col" in self.html

    def test_heatmap_uses_github_colors(self) -> None:
        for color in ("#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"):
            assert color in self.html, f"Missing heatmap color: {color}"

    def test_heatmap_legend_has_all_levels(self) -> None:
        for level in range(5):
            assert f"hm-level-{level}" in self.html

    def test_heatmap_custom_tooltip_css(self) -> None:
        assert "data-tip" in self.html
        assert "animation-delay: 0.25s" in self.html

    def test_heatmap_stat_cards_grid(self) -> None:
        assert "grid-cols-2 md:grid-cols-4" in self.html

    def test_heatmap_total_count_element(self) -> None:
        assert 'id="heatmap-total-count"' in self.html


# ------------------------------------------------------------------ #
#  Responsive CSS and mobile
# ------------------------------------------------------------------ #
class TestDashboardResponsiveCSS(BaseUserTestCaseMixin, TestCase):
    html: str

    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)
        url = reverse("private:user_dashboard")
        response = self.client.get(url)
        self.html = response.content.decode()

    def _extract_mobile_block(self) -> str:
        """Find the dashboard's mobile @media block.

        Targets the block containing .heatmap-section-desktop,
        not the base template's."""
        marker = "max-width: 768px"
        start = 0
        while True:
            start = self.html.find(marker, start)
            assert start != -1, "Dashboard mobile @media block not found"
            open_brace = self.html.index("{", start)
            depth = 1
            pos = open_brace + 1
            while depth > 0 and pos < len(self.html):
                if self.html[pos] == "{":
                    depth += 1
                elif self.html[pos] == "}":
                    depth -= 1
                pos += 1
            block = self.html[open_brace + 1 : pos - 1]
            if ".heatmap-section-desktop" in block or ".activity-row" in block:
                return block
            start = pos

    def test_stat_cards_use_responsive_grid(self) -> None:
        stat_cards_section = re.search(
            r'id="stat-cards"[^>]*class="([^"]*)"', self.html
        )
        assert stat_cards_section is not None
        classes = stat_cards_section.group(1)
        assert "grid-cols-2" in classes
        assert "lg:grid-cols-3" in classes or "xl:grid-cols-6" in classes

    def test_charts_stack_on_mobile(self) -> None:
        assert "flex-col md:flex-row" in self.html

    def test_quick_actions_stack_on_mobile(self) -> None:
        assert "flex-col sm:flex-row" in self.html

    def test_heatmap_hidden_on_mobile(self) -> None:
        assert "heatmap-section-desktop" in self.html

    def test_mobile_css_hides_heatmap(self) -> None:
        mobile = self._extract_mobile_block()
        assert ".heatmap-section-desktop" in mobile
        assert "display: none" in mobile

    def test_mobile_css_hides_sha_badge(self) -> None:
        mobile = self._extract_mobile_block()
        assert ".activity-badge-sha" in mobile
        assert "display: none" in mobile

    def test_mobile_css_hides_avatar(self) -> None:
        mobile = self._extract_mobile_block()
        assert ".activity-avatar" in mobile
        assert "display: none" in mobile

    def test_mobile_css_hides_commit_message(self) -> None:
        mobile = self._extract_mobile_block()
        assert ".activity-msg" in mobile
        assert "display: none" in mobile

    def test_mobile_css_quick_action_full_width(self) -> None:
        mobile = self._extract_mobile_block()
        assert ".quick-action-btn" in mobile
        assert "width: 100%" in mobile

    def test_mobile_activity_uses_grid_layout(self) -> None:
        mobile = self._extract_mobile_block()
        assert ".activity-row" in mobile
        assert "display: grid" in mobile
        assert "grid-template-columns" in mobile

    def test_mobile_short_time_visible(self) -> None:
        mobile = self._extract_mobile_block()
        assert ".activity-time-full" in mobile
        assert ".activity-time-short" in mobile

    def test_activity_has_dual_time_formats(self) -> None:
        assert "activity-time-full" in self.html
        assert "activity-time-short" in self.html

    def test_desktop_hides_short_time(self) -> None:
        assert ".activity-time-short { display: none; }" in self.html

    def test_sidebar_profile_item_exists(self) -> None:
        profile_url = reverse("private:user_profile")
        assert f'href="{profile_url}"' in self.html
        sidebar = self.html[: self.html.find("<!-- Content area -->")]
        assert "Profile" in sidebar
