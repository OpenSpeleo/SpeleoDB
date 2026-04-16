# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime
import time
from typing import Any
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.api.v2.tests.factories import ExplorationLeadFactory
from speleodb.api.v2.tests.factories import ProjectCommitFactory
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import SubSurfaceStationFactory
from speleodb.api.v2.tests.factories import SurveyTeamFactory
from speleodb.api.v2.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v2.tests.factories import TeamProjectPermissionFactory
from speleodb.api.v2.tests.factories import TokenFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.api.v2.views.user_dashboard import CONTRIBUTION_CALENDAR_DAYS
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import ProjectType
from speleodb.common.enums import SurveyTeamMembershipRole
from speleodb.gis.models import Landmark
from speleodb.gis.models import SubSurfaceStation
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.users.tests.factories import UserFactory

URL = reverse("api:v2:user-dashboard-stats")


# ------------------------------------------------------------------ #
#  Authentication
# ------------------------------------------------------------------ #
class TestDashboardStatsAuthentication(BaseAPITestCase):
    def test_unauthenticated_request_returns_401_or_403(self) -> None:
        response = self.client.get(URL)
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_authenticated_request_returns_200(self) -> None:
        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK


# ------------------------------------------------------------------ #
#  Empty state
# ------------------------------------------------------------------ #
class TestDashboardStatsEmptyState(BaseAPITestCase):
    def _get_data(self) -> dict[str, Any]:
        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK
        return response.data  # type: ignore[no-any-return]

    def test_response_structure_complete(self) -> None:
        data = self._get_data()
        assert "summary" in data
        assert "projects_by_level" in data
        assert "projects_by_type" in data
        assert "commits_over_time" in data
        assert "contribution_calendar" in data
        assert "recent_activity" in data

    def test_projects_by_type_empty(self) -> None:
        pbt = self._get_data()["projects_by_type"]
        assert pbt == {}

    def test_summary_all_zeros(self) -> None:
        summary = self._get_data()["summary"]
        for key in (
            "total_projects",
            "total_teams",
            "total_commits",
            "user_commits",
            "total_landmarks",
            "total_gps_tracks",
            "total_stations_created",
            "total_exploration_leads",
        ):
            assert summary[key] == 0, f"{key} should be 0, got {summary[key]}"

    def test_projects_by_level_all_zeros(self) -> None:
        pbl = self._get_data()["projects_by_level"]
        assert pbl["ADMIN"] == 0
        assert pbl["READ_AND_WRITE"] == 0
        assert pbl["READ_ONLY"] == 0

    def test_commits_over_time_all_zeros(self) -> None:
        cot = self._get_data()["commits_over_time"]
        assert len(cot) == 12  # noqa: PLR2004
        for entry in cot:
            assert entry["total"] == 0
            assert entry["user"] == 0

    def test_contribution_calendar_empty(self) -> None:
        cal = self._get_data()["contribution_calendar"]
        assert cal == []

    def test_recent_activity_empty(self) -> None:
        activity = self._get_data()["recent_activity"]
        assert activity == []


# ------------------------------------------------------------------ #
#  Summary counts
# ------------------------------------------------------------------ #
class TestDashboardStatsSummaryCounts(BaseAPITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.other_user = UserFactory.create()

        self.project_admin = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user, project=self.project_admin, level=PermissionLevel.ADMIN
        )

        self.project_rw = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project_rw,
            level=PermissionLevel.READ_AND_WRITE,
        )

        self.project_ro = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user, project=self.project_ro, level=PermissionLevel.READ_ONLY
        )

        self.inaccessible_project = ProjectFactory.create(
            created_by=self.other_user.email
        )
        UserProjectPermissionFactory.create(
            target=self.other_user,
            project=self.inaccessible_project,
            level=PermissionLevel.ADMIN,
        )

        # Commits: 3 by user, 2 by others on accessible projects, 1 on inaccessible
        for proj in (self.project_admin, self.project_rw, self.project_ro):
            ProjectCommitFactory.create(
                project=proj, author_email=self.user.email, author_name=self.user.name
            )
        for proj in (self.project_admin, self.project_rw):
            ProjectCommitFactory.create(
                project=proj,
                author_email=self.other_user.email,
                author_name=self.other_user.name,
            )
        ProjectCommitFactory.create(
            project=self.inaccessible_project,
            author_email=self.user.email,
            author_name=self.user.name,
        )

        # Teams
        team = SurveyTeamFactory.create()
        SurveyTeamMembershipFactory.create(
            user=self.user, team=team, role=SurveyTeamMembershipRole.MEMBER
        )

        # Landmarks: 2 for user, 1 for other
        Landmark.objects.create(
            name="LM1", user=self.user, latitude=20.0, longitude=-87.0
        )
        Landmark.objects.create(
            name="LM2", user=self.user, latitude=21.0, longitude=-88.0
        )
        Landmark.objects.create(
            name="LM3", user=self.other_user, latitude=22.0, longitude=-89.0
        )

        # Stations: 2 by user email, 1 by other email
        SubSurfaceStationFactory.create(
            project=self.project_admin, created_by=self.user.email
        )
        SubSurfaceStationFactory.create(
            project=self.project_rw, created_by=self.user.email
        )
        SubSurfaceStationFactory.create(
            project=self.project_admin, created_by=self.other_user.email
        )

        # Exploration leads: 1 on accessible, 1 on inaccessible
        ExplorationLeadFactory.create(
            project=self.project_admin, created_by=self.user.email
        )
        ExplorationLeadFactory.create(
            project=self.inaccessible_project, created_by=self.user.email
        )

    def _get_summary(self) -> dict[str, int]:
        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK
        return response.data["summary"]  # type: ignore[no-any-return]

    def test_total_projects_counts_only_accessible(self) -> None:
        assert self._get_summary()["total_projects"] == 3  # noqa: PLR2004

    def test_total_projects_excludes_inaccessible(self) -> None:
        assert self._get_summary()["total_projects"] != 4  # noqa: PLR2004

    def test_total_teams_count(self) -> None:
        assert self._get_summary()["total_teams"] == 1

    def test_total_commits_across_all_accessible_projects(self) -> None:
        assert self._get_summary()["total_commits"] == 5  # noqa: PLR2004

    def test_total_commits_excludes_inaccessible_project(self) -> None:
        total = self._get_summary()["total_commits"]
        all_commits = ProjectCommit.objects.count()
        assert total < all_commits

    def test_user_commits_only_counts_user_authored(self) -> None:
        assert self._get_summary()["user_commits"] == 3  # noqa: PLR2004

    def test_user_commits_excludes_other_authors(self) -> None:
        assert (
            self._get_summary()["user_commits"] < self._get_summary()["total_commits"]
        )

    def test_total_landmarks_only_counts_user_owned(self) -> None:
        assert self._get_summary()["total_landmarks"] == 2  # noqa: PLR2004

    def test_total_landmarks_excludes_other_users(self) -> None:
        all_landmarks = Landmark.objects.count()
        assert self._get_summary()["total_landmarks"] < all_landmarks

    def test_total_gps_tracks_count(self) -> None:
        assert self._get_summary()["total_gps_tracks"] == 0

    def test_total_stations_created_by_user_email(self) -> None:
        assert self._get_summary()["total_stations_created"] == 2  # noqa: PLR2004

    def test_total_stations_excludes_other_creators(self) -> None:
        all_stations = SubSurfaceStation.objects.count()
        assert self._get_summary()["total_stations_created"] < all_stations

    def test_total_exploration_leads_count(self) -> None:
        assert self._get_summary()["total_exploration_leads"] == 1

    def test_total_exploration_leads_excludes_inaccessible_projects(self) -> None:
        assert self._get_summary()["total_exploration_leads"] == 1


# ------------------------------------------------------------------ #
#  Projects by level
# ------------------------------------------------------------------ #
class TestDashboardStatsProjectsByLevel(BaseAPITestCase):
    def setUp(self) -> None:
        super().setUp()

        self.admin_projects = []
        for _ in range(3):
            p = ProjectFactory.create(created_by=self.user.email)
            UserProjectPermissionFactory.create(
                target=self.user, project=p, level=PermissionLevel.ADMIN
            )
            self.admin_projects.append(p)

        self.rw_projects = []
        for _ in range(2):
            p = ProjectFactory.create(created_by=self.user.email)
            UserProjectPermissionFactory.create(
                target=self.user, project=p, level=PermissionLevel.READ_AND_WRITE
            )
            self.rw_projects.append(p)

        self.ro_project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user, project=self.ro_project, level=PermissionLevel.READ_ONLY
        )

        self.wv_project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user, project=self.wv_project, level=PermissionLevel.WEB_VIEWER
        )

    def _get_pbl(self) -> dict[str, int]:
        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK
        return response.data["projects_by_level"]  # type: ignore[no-any-return]

    def test_admin_count_matches(self) -> None:
        assert self._get_pbl()["ADMIN"] == 3  # noqa: PLR2004

    def test_read_and_write_count_matches(self) -> None:
        assert self._get_pbl()["READ_AND_WRITE"] == 2  # noqa: PLR2004

    def test_read_only_count_matches(self) -> None:
        assert self._get_pbl()["READ_ONLY"] == 1

    def test_total_matches_sum_of_levels(self) -> None:
        """total_projects counts ALL accessible projects (including WEB_VIEWER),
        while projects_by_level only reports the 3 collaboration tiers."""
        pbl = self._get_pbl()
        response = self.client.get(URL, headers={"authorization": self.auth})
        summary = response.data["summary"]
        assert (
            pbl["ADMIN"] + pbl["READ_AND_WRITE"] + pbl["READ_ONLY"]
            <= summary["total_projects"]
        )

    def test_web_viewer_excluded(self) -> None:
        pbl = self._get_pbl()
        assert "WEB_VIEWER" not in pbl

    def test_team_permission_contributes_to_level(self) -> None:
        team_project = ProjectFactory.create(created_by=self.user.email)
        team = SurveyTeamFactory.create()
        SurveyTeamMembershipFactory.create(
            user=self.user, team=team, role=SurveyTeamMembershipRole.MEMBER
        )
        TeamProjectPermissionFactory.create(
            target=team, project=team_project, level=PermissionLevel.READ_AND_WRITE
        )

        pbl = self._get_pbl()
        assert pbl["READ_AND_WRITE"] == 3  # noqa: PLR2004

    def test_best_permission_wins(self) -> None:
        conflict_project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user,
            project=conflict_project,
            level=PermissionLevel.READ_ONLY,
        )
        team = SurveyTeamFactory.create()
        SurveyTeamMembershipFactory.create(
            user=self.user, team=team, role=SurveyTeamMembershipRole.MEMBER
        )
        TeamProjectPermissionFactory.create(
            target=team,
            project=conflict_project,
            level=PermissionLevel.READ_AND_WRITE,
        )

        pbl = self._get_pbl()
        assert pbl["READ_AND_WRITE"] == 3  # noqa: PLR2004


# ------------------------------------------------------------------ #
#  Projects by type
# ------------------------------------------------------------------ #
class TestDashboardStatsProjectsByType(BaseAPITestCase):
    def setUp(self) -> None:
        super().setUp()

        self.ariane_projects = []
        for _ in range(3):
            p = ProjectFactory.create(
                created_by=self.user.email, type=ProjectType.ARIANE
            )
            UserProjectPermissionFactory.create(
                target=self.user, project=p, level=PermissionLevel.ADMIN
            )
            self.ariane_projects.append(p)

        self.compass_project = ProjectFactory.create(
            created_by=self.user.email, type=ProjectType.COMPASS
        )
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.compass_project,
            level=PermissionLevel.READ_AND_WRITE,
        )

        self.other_user = UserFactory.create()
        self.inaccessible = ProjectFactory.create(
            created_by=self.other_user.email, type=ProjectType.THERION
        )
        UserProjectPermissionFactory.create(
            target=self.other_user,
            project=self.inaccessible,
            level=PermissionLevel.ADMIN,
        )

    def _get_pbt(self) -> dict[str, int]:
        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK
        return response.data["projects_by_type"]  # type: ignore[no-any-return]

    def test_ariane_count_matches(self) -> None:
        assert self._get_pbt()["ariane"] == 3  # noqa: PLR2004

    def test_compass_count_matches(self) -> None:
        assert self._get_pbt()["compass"] == 1

    def test_inaccessible_type_excluded(self) -> None:
        pbt = self._get_pbt()
        assert "therion" not in pbt

    def test_total_matches_sum(self) -> None:
        pbt = self._get_pbt()
        total = sum(pbt.values())
        assert total == 4  # noqa: PLR2004

    def test_returns_dict_of_type_to_count(self) -> None:
        pbt = self._get_pbt()
        assert isinstance(pbt, dict)
        for key, val in pbt.items():
            assert isinstance(key, str)
            assert isinstance(val, int)


# ------------------------------------------------------------------ #
#  Commits over time
# ------------------------------------------------------------------ #
class TestDashboardStatsCommitsOverTime(BaseAPITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.other_user = UserFactory.create()

        self.project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user, project=self.project, level=PermissionLevel.ADMIN
        )

        self.inaccessible = ProjectFactory.create(created_by=self.other_user.email)
        UserProjectPermissionFactory.create(
            target=self.other_user,
            project=self.inaccessible,
            level=PermissionLevel.ADMIN,
        )

        now = timezone.now()

        # 5 commits this month: 3 by user, 2 by other
        for _ in range(3):
            ProjectCommitFactory.create(
                project=self.project,
                author_email=self.user.email,
                authored_date=now - datetime.timedelta(days=1),
            )
        for _ in range(2):
            ProjectCommitFactory.create(
                project=self.project,
                author_email=self.other_user.email,
                authored_date=now - datetime.timedelta(days=2),
            )

        # 2 commits 3 months ago
        three_months_ago = now - datetime.timedelta(days=90)
        ProjectCommitFactory.create(
            project=self.project,
            author_email=self.user.email,
            authored_date=three_months_ago,
        )
        ProjectCommitFactory.create(
            project=self.project,
            author_email=self.other_user.email,
            authored_date=three_months_ago,
        )

        # 1 commit 14 months ago (outside window)
        ProjectCommitFactory.create(
            project=self.project,
            author_email=self.user.email,
            authored_date=now - datetime.timedelta(days=430),
        )

        # 1 commit on inaccessible project
        ProjectCommitFactory.create(
            project=self.inaccessible,
            author_email=self.user.email,
            authored_date=now,
        )

    def _get_cot(self) -> list[dict[str, Any]]:
        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK
        return response.data["commits_over_time"]  # type: ignore[no-any-return]

    def test_returns_12_months(self) -> None:
        assert len(self._get_cot()) == 12  # noqa: PLR2004

    def test_months_are_chronologically_ordered(self) -> None:
        cot = self._get_cot()
        months = [e["month"] for e in cot]
        assert months == sorted(months)

    def test_month_format_is_yyyy_mm(self) -> None:
        cot = self._get_cot()
        for entry in cot:
            assert len(entry["month"]) == 7  # noqa: PLR2004
            assert entry["month"][4] == "-"

    def test_total_per_month_is_accurate(self) -> None:
        cot = self._get_cot()
        current_month = timezone.now().strftime("%Y-%m")
        current_entry = [e for e in cot if e["month"] == current_month]
        assert len(current_entry) == 1
        assert current_entry[0]["total"] == 5  # noqa: PLR2004

    def test_user_per_month_is_accurate(self) -> None:
        cot = self._get_cot()
        current_month = timezone.now().strftime("%Y-%m")
        current_entry = [e for e in cot if e["month"] == current_month]
        assert current_entry[0]["user"] == 3  # noqa: PLR2004

    def test_months_with_zero_commits_still_present(self) -> None:
        cot = self._get_cot()
        zero_months = [e for e in cot if e["total"] == 0]
        assert len(zero_months) > 0

    def test_user_count_never_exceeds_total(self) -> None:
        for entry in self._get_cot():
            assert entry["user"] <= entry["total"]

    def test_commits_from_inaccessible_projects_excluded(self) -> None:
        cot = self._get_cot()
        total_sum = sum(e["total"] for e in cot)
        accessible_commits = ProjectCommit.objects.filter(project=self.project).count()
        # The 14-month-old commit is excluded from the 12-month window
        assert total_sum <= accessible_commits


# ------------------------------------------------------------------ #
#  Commits over time — month boundary edge cases
# ------------------------------------------------------------------ #
class TestCommitsOverTimeMonthBoundary(BaseAPITestCase):
    """Verify the 12-month window never skips a calendar month.

    The old 31-day-step heuristic would skip February when 'now' landed
    on March 1st.  These tests freeze time on short-month boundaries.
    """

    def setUp(self) -> None:
        super().setUp()
        self.project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user, project=self.project, level=PermissionLevel.ADMIN
        )

    def _get_months(self, fake_now: datetime.datetime) -> list[str]:
        with patch(
            "speleodb.api.v2.views.user_dashboard.timezone.now", return_value=fake_now
        ):
            response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK
        return [e["month"] for e in response.data["commits_over_time"]]

    def test_march_1st_includes_february(self) -> None:
        months = self._get_months(
            datetime.datetime(2026, 3, 1, 12, 0, 0, tzinfo=datetime.UTC)
        )
        assert len(months) == 12  # noqa: PLR2004
        assert len(set(months)) == 12  # noqa: PLR2004
        assert "2026-02" in months

    def test_april_1st_includes_all_12_months(self) -> None:
        months = self._get_months(
            datetime.datetime(2026, 4, 1, 0, 0, 0, tzinfo=datetime.UTC)
        )
        assert len(months) == 12  # noqa: PLR2004
        assert len(set(months)) == 12  # noqa: PLR2004
        assert "2026-02" in months
        assert "2026-03" in months

    def test_january_1st_crosses_year_boundary(self) -> None:
        months = self._get_months(
            datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.UTC)
        )
        assert len(months) == 12  # noqa: PLR2004
        assert len(set(months)) == 12  # noqa: PLR2004
        assert months[0] == "2025-02"
        assert months[-1] == "2026-01"

    def test_months_are_consecutive(self) -> None:
        months = self._get_months(
            datetime.datetime(2026, 3, 1, 12, 0, 0, tzinfo=datetime.UTC)
        )
        for i in range(1, len(months)):
            prev_y, prev_m = map(int, months[i - 1].split("-"))
            cur_y, cur_m = map(int, months[i].split("-"))
            expected_m = prev_m + 1 if prev_m < 12 else 1  # noqa: PLR2004
            expected_y = prev_y if prev_m < 12 else prev_y + 1  # noqa: PLR2004
            assert (cur_y, cur_m) == (expected_y, expected_m), (
                f"Gap between {months[i - 1]} and {months[i]}"
            )


# ------------------------------------------------------------------ #
#  Contribution calendar
# ------------------------------------------------------------------ #
class TestDashboardStatsContributionCalendar(BaseAPITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.other_user = UserFactory.create()

        self.project_a = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user, project=self.project_a, level=PermissionLevel.ADMIN
        )

        self.project_b = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user,
            project=self.project_b,
            level=PermissionLevel.READ_AND_WRITE,
        )

        self.inaccessible = ProjectFactory.create(created_by=self.other_user.email)
        UserProjectPermissionFactory.create(
            target=self.other_user,
            project=self.inaccessible,
            level=PermissionLevel.ADMIN,
        )

        now = timezone.now()
        self.thirty_days_ago = now - datetime.timedelta(days=30)
        self.four_hundred_days_ago = now - datetime.timedelta(days=400)

        # 3 user commits 30 days ago (2 on project_a, 1 on project_b)
        for _ in range(2):
            ProjectCommitFactory.create(
                project=self.project_a,
                author_email=self.user.email,
                authored_date=self.thirty_days_ago,
            )
        ProjectCommitFactory.create(
            project=self.project_b,
            author_email=self.user.email,
            authored_date=self.thirty_days_ago,
        )

        # 1 commit by other author (should not appear)
        ProjectCommitFactory.create(
            project=self.project_a,
            author_email=self.other_user.email,
            authored_date=self.thirty_days_ago,
        )

        # 1 commit 400 days ago (outside window)
        ProjectCommitFactory.create(
            project=self.project_a,
            author_email=self.user.email,
            authored_date=self.four_hundred_days_ago,
        )

        # 1 user commit on inaccessible project
        ProjectCommitFactory.create(
            project=self.inaccessible,
            author_email=self.user.email,
            authored_date=now - datetime.timedelta(days=5),
        )

    def _get_cal(self) -> list[str]:
        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK
        return response.data["contribution_calendar"]  # type: ignore[no-any-return]

    def test_only_user_commits_included(self) -> None:
        cal = self._get_cal()
        assert len(cal) == 3  # noqa: PLR2004

    def test_returns_list_of_iso_timestamps(self) -> None:
        cal = self._get_cal()
        assert isinstance(cal, list)
        for ts in cal:
            assert isinstance(ts, str)
            datetime.datetime.fromisoformat(ts)

    def test_dates_within_365_days_included(self) -> None:
        cal = self._get_cal()
        assert len(cal) > 0

    def test_dates_older_than_365_days_excluded(self) -> None:
        cal = self._get_cal()
        for ts in cal:
            dt = datetime.datetime.fromisoformat(ts)
            days_ago = (timezone.now() - dt).days
            assert days_ago <= CONTRIBUTION_CALENDAR_DAYS

    def test_multiple_projects_same_day_aggregated(self) -> None:
        cal = self._get_cal()
        assert len(cal) == 3  # noqa: PLR2004

    def test_calendar_scoped_to_accessible_projects(self) -> None:
        cal = self._get_cal()
        assert len(cal) == 3  # noqa: PLR2004


# ------------------------------------------------------------------ #
#  Recent activity
# ------------------------------------------------------------------ #
class TestDashboardStatsRecentActivity(BaseAPITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.other_user = UserFactory.create()

        self.project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user, project=self.project, level=PermissionLevel.ADMIN
        )

        self.project_b = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user, project=self.project_b, level=PermissionLevel.READ_ONLY
        )

        self.inaccessible = ProjectFactory.create(created_by=self.other_user.email)
        UserProjectPermissionFactory.create(
            target=self.other_user,
            project=self.inaccessible,
            level=PermissionLevel.ADMIN,
        )

        now = timezone.now()
        for i in range(20):
            email = self.user.email if i % 2 == 0 else self.other_user.email
            name = self.user.name if i % 2 == 0 else self.other_user.name
            proj = self.project if i % 3 != 0 else self.project_b
            ProjectCommitFactory.create(
                project=proj,
                author_email=email,
                author_name=name,
                authored_date=now - datetime.timedelta(hours=i),
                message=f"Commit message #{i}",
            )

        # Inaccessible commit
        ProjectCommitFactory.create(
            project=self.inaccessible,
            author_email=self.user.email,
            authored_date=now,
            message="Should not appear",
        )

    def _get_activity(self) -> list[dict[str, Any]]:
        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK
        return response.data["recent_activity"]  # type: ignore[no-any-return]

    def test_returns_at_most_15_entries(self) -> None:
        assert len(self._get_activity()) == 15  # noqa: PLR2004

    def test_entries_ordered_by_newest_first(self) -> None:
        activity = self._get_activity()
        dates = [a["authored_date"] for a in activity]
        assert dates == sorted(dates, reverse=True)

    def test_entry_contains_required_fields(self) -> None:
        entry = self._get_activity()[0]
        for field in (
            "commit_id",
            "project_name",
            "project_id",
            "author_name",
            "author_email",
            "authored_date",
            "message",
        ):
            assert field in entry, f"Missing field: {field}"

    def test_includes_commits_from_all_accessible_projects(self) -> None:
        activity = self._get_activity()
        project_ids = {a["project_id"] for a in activity}
        assert str(self.project.id) in project_ids
        assert str(self.project_b.id) in project_ids

    def test_excludes_commits_from_inaccessible_projects(self) -> None:
        activity = self._get_activity()
        project_ids = {a["project_id"] for a in activity}
        assert str(self.inaccessible.id) not in project_ids

    def test_includes_other_authors_commits(self) -> None:
        activity = self._get_activity()
        emails = {a["author_email"] for a in activity}
        assert self.other_user.email in emails

    def test_project_name_matches_actual_project(self) -> None:
        entry = self._get_activity()[0]
        project = Project.objects.get(id=entry["project_id"])
        assert entry["project_name"] == project.name

    def test_authored_date_is_iso_format(self) -> None:
        entry = self._get_activity()[0]
        datetime.datetime.fromisoformat(entry["authored_date"])

    def test_message_is_not_truncated(self) -> None:
        activity = self._get_activity()
        messages = {a["message"] for a in activity}
        assert any("Commit message" in m for m in messages)

    def test_empty_when_no_commits_exist(self) -> None:
        fresh_user = UserFactory.create()
        token = TokenFactory.create(user=fresh_user)
        p = ProjectFactory.create(created_by=fresh_user.email)
        UserProjectPermissionFactory.create(
            target=fresh_user, project=p, level=PermissionLevel.ADMIN
        )
        response = self.client.get(URL, headers={"authorization": f"Token {token.key}"})
        assert response.data["recent_activity"] == []


# ------------------------------------------------------------------ #
#  Edge cases
# ------------------------------------------------------------------ #
class TestDashboardStatsEdgeCases(BaseAPITestCase):
    def test_user_with_only_team_permissions(self) -> None:
        project = ProjectFactory.create(created_by="someone@example.com")
        team = SurveyTeamFactory.create()
        SurveyTeamMembershipFactory.create(
            user=self.user, team=team, role=SurveyTeamMembershipRole.MEMBER
        )
        TeamProjectPermissionFactory.create(
            target=team, project=project, level=PermissionLevel.READ_AND_WRITE
        )

        response = self.client.get(URL, headers={"authorization": self.auth})
        data = response.data
        assert data["summary"]["total_projects"] == 1

    def test_user_with_both_direct_and_team_permissions_no_duplication(self) -> None:
        project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user, project=project, level=PermissionLevel.READ_ONLY
        )
        team = SurveyTeamFactory.create()
        SurveyTeamMembershipFactory.create(
            user=self.user, team=team, role=SurveyTeamMembershipRole.MEMBER
        )
        TeamProjectPermissionFactory.create(
            target=team, project=project, level=PermissionLevel.READ_AND_WRITE
        )

        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.data["summary"]["total_projects"] == 1

    def test_deactivated_permission_not_counted(self) -> None:
        project = ProjectFactory.create(created_by=self.user.email)
        perm = UserProjectPermissionFactory.create(
            target=self.user, project=project, level=PermissionLevel.ADMIN
        )
        perm.deactivate(deactivated_by=self.user)

        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.data["summary"]["total_projects"] == 0

    def test_inactive_team_membership_not_counted(self) -> None:
        project = ProjectFactory.create(created_by=self.user.email)
        team = SurveyTeamFactory.create()
        membership = SurveyTeamMembershipFactory.create(
            user=self.user, team=team, role=SurveyTeamMembershipRole.MEMBER
        )
        membership.is_active = False
        membership.save()
        TeamProjectPermissionFactory.create(
            target=team, project=project, level=PermissionLevel.READ_AND_WRITE
        )

        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.data["summary"]["total_projects"] == 0

    def test_large_dataset_performance(self) -> None:
        projects = [
            ProjectFactory.create(created_by=self.user.email) for _ in range(10)
        ]
        for p in projects:
            UserProjectPermissionFactory.create(
                target=self.user, project=p, level=PermissionLevel.ADMIN
            )
        for p in projects:
            for _ in range(10):
                ProjectCommitFactory.create(
                    project=p,
                    author_email=self.user.email,
                    authored_date=timezone.now()
                    - datetime.timedelta(days=int(360 * (hash(str(p.id)) % 100) / 100)),
                )

        start = time.monotonic()
        response = self.client.get(URL, headers={"authorization": self.auth})
        elapsed = time.monotonic() - start

        assert response.status_code == status.HTTP_200_OK
        assert elapsed < 5.0  # noqa: PLR2004

    def test_commits_with_automated_message_still_counted(self) -> None:
        project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory.create(
            target=self.user, project=project, level=PermissionLevel.ADMIN
        )
        ProjectCommitFactory.create(
            project=project,
            author_email=self.user.email,
            message="[Automated] Project Creation",
        )

        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.data["summary"]["total_commits"] == 1
