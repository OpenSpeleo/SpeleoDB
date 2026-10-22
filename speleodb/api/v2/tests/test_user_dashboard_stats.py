# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime as dt
from typing import Any
from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.api.v2.tests.factories import ExplorationLeadFactory
from speleodb.api.v2.tests.factories import GPSTrackFactory
from speleodb.api.v2.tests.factories import GPSTrackUserPermissionFactory
from speleodb.api.v2.tests.factories import ProjectCommitFactory
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import SubSurfaceStationFactory
from speleodb.api.v2.tests.factories import SurveyTeamFactory
from speleodb.api.v2.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v2.tests.factories import TeamProjectPermissionFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import ProjectType
from speleodb.common.enums import SurveyTeamMembershipRole
from speleodb.gis.landmark_collections import get_or_create_personal_landmark_collection
from speleodb.gis.models import Landmark
from speleodb.users.tests.factories import UserFactory

URL = reverse("api:v2:user-dashboard-stats")


# ------------------------------------------------------------------ #
#  Authentication
# ------------------------------------------------------------------ #
class TestDashboardStatsAuthentication(BaseAPITestCase):
    def test_unauthenticated_request_is_forbidden(self) -> None:
        response = self.client.get(URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ------------------------------------------------------------------ #
#  Empty state
# ------------------------------------------------------------------ #
class TestDashboardStatsEmptyState(BaseAPITestCase):
    def _get_data(self) -> dict[str, Any]:
        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK
        return response.data  # type: ignore[no-any-return]

    def test_empty_dashboard(self) -> None:
        data = self._get_data()
        assert data["summary"] == {
            "total_projects": 0,
            "total_teams": 0,
            "total_commits": 0,
            "user_commits": 0,
            "total_landmarks": 0,
            "total_gps_tracks": 0,
            "total_stations_created": 0,
            "total_exploration_leads": 0,
        }
        assert data["projects_by_level"] == {
            "ADMIN": 0,
            "READ_AND_WRITE": 0,
            "READ_ONLY": 0,
        }
        assert data["projects_by_type"] == {}
        assert len(data["commits_over_time"]) == 12  # noqa: PLR2004
        assert all(
            row["total"] == row["user"] == 0 for row in data["commits_over_time"]
        )
        assert data["contribution_calendar"] == []
        assert data["recent_activity"] == []


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

        # Landmarks: 2 in user's personal collection, 1 in another user's.
        user_personal_collection = get_or_create_personal_landmark_collection(
            user=self.user
        )
        other_personal_collection = get_or_create_personal_landmark_collection(
            user=self.other_user
        )
        Landmark.objects.create(
            name="LM1",
            created_by=self.user.email,
            collection=user_personal_collection,
            latitude=20.0,
            longitude=-87.0,
        )
        Landmark.objects.create(
            name="LM2",
            created_by=self.user.email,
            collection=user_personal_collection,
            latitude=21.0,
            longitude=-88.0,
        )
        Landmark.objects.create(
            name="LM3",
            created_by=self.other_user.email,
            collection=other_personal_collection,
            latitude=22.0,
            longitude=-89.0,
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

    def test_summary_counts_respect_access_and_ownership(self) -> None:
        assert self._get_summary() == {
            "total_projects": 3,
            "total_teams": 1,
            "total_commits": 5,
            "user_commits": 3,
            "total_landmarks": 2,
            "total_gps_tracks": 0,
            "total_stations_created": 2,
            "total_exploration_leads": 1,
        }


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

    def test_levels_exclude_web_viewers_but_total_includes_them(self) -> None:
        """total_projects counts ALL accessible projects (including WEB_VIEWER),
        while projects_by_level only reports the 3 collaboration tiers."""
        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["projects_by_level"] == {
            "ADMIN": 3,
            "READ_AND_WRITE": 2,
            "READ_ONLY": 1,
        }
        assert response.data["summary"]["total_projects"] == 7  # noqa: PLR2004

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

    def test_type_counts_exclude_inaccessible_projects(self) -> None:
        assert self._get_pbt() == {"ariane": 3, "compass": 1}


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

        now = timezone.localtime(timezone.now())
        current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # 5 commits this month: 3 by user, 2 by other
        for _ in range(3):
            ProjectCommitFactory.create(
                project=self.project,
                author_email=self.user.email,
                authored_date=current_month,
            )
        for _ in range(2):
            ProjectCommitFactory.create(
                project=self.project,
                author_email=self.other_user.email,
                authored_date=current_month,
            )

        # 2 commits 3 months ago
        three_months_ago = now - dt.timedelta(days=90)
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
            authored_date=now - dt.timedelta(days=430),
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

    def test_monthly_counts_include_zeros_and_exclude_old_or_inaccessible_commits(
        self,
    ) -> None:
        rows = self._get_cot()
        months = [row["month"] for row in rows]
        assert len(months) == len(set(months)) == 12  # noqa: PLR2004
        assert months == sorted(months)
        current_month = timezone.localtime(timezone.now()).strftime("%Y-%m")
        assert rows[-1] == {"month": current_month, "total": 5, "user": 3}
        assert sum(row["total"] for row in rows) == 7  # noqa: PLR2004
        assert sum(row["user"] for row in rows) == 4  # noqa: PLR2004
        assert sum(row["total"] == row["user"] == 0 for row in rows) == 10  # noqa: PLR2004


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

    def _get_months(self, fake_now: dt.datetime) -> list[str]:
        with patch(
            "speleodb.api.v2.views.user_dashboard.timezone.now", return_value=fake_now
        ):
            response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK
        return [e["month"] for e in response.data["commits_over_time"]]

    def test_march_1st_includes_every_month_once(self) -> None:
        months = self._get_months(dt.datetime(2026, 3, 1, 12, 0, 0, tzinfo=dt.UTC))
        assert months == [
            "2025-04",
            "2025-05",
            "2025-06",
            "2025-07",
            "2025-08",
            "2025-09",
            "2025-10",
            "2025-11",
            "2025-12",
            "2026-01",
            "2026-02",
            "2026-03",
        ]

    def test_january_1st_crosses_year_boundary(self) -> None:
        months = self._get_months(dt.datetime(2026, 1, 1, 12, 0, 0, tzinfo=dt.UTC))
        assert len(months) == 12  # noqa: PLR2004
        assert len(set(months)) == 12  # noqa: PLR2004
        assert months[0] == "2025-02"
        assert months[-1] == "2026-01"


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
        self.thirty_days_ago = now - dt.timedelta(days=30)
        self.four_hundred_days_ago = now - dt.timedelta(days=400)

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
            authored_date=now - dt.timedelta(days=5),
        )

    def _get_cal(self) -> list[str]:
        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK
        return response.data["contribution_calendar"]  # type: ignore[no-any-return]

    def test_calendar_includes_only_recent_user_commits_on_accessible_projects(
        self,
    ) -> None:
        assert self._get_cal() == [self.thirty_days_ago.isoformat()] * 3


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
                authored_date=now - dt.timedelta(hours=i),
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

    def test_recent_activity_is_bounded_ordered_and_scoped_to_accessible_projects(
        self,
    ) -> None:
        activity = self._get_activity()
        assert len(activity) == 15  # noqa: PLR2004
        assert [entry["message"] for entry in activity] == [
            f"Commit message #{i}" for i in range(15)
        ]
        dates = [entry["authored_date"] for entry in activity]
        assert dates == sorted(dates, reverse=True)
        for i, entry in enumerate(activity):
            project = self.project if i % 3 != 0 else self.project_b
            author = self.user if i % 2 == 0 else self.other_user
            assert entry["project_id"] == str(project.id)
            assert entry["project_name"] == project.name
            assert entry["author_name"] == author.name
            assert entry["author_email"] == author.email
            assert entry["commit_id"]
            dt.datetime.fromisoformat(entry["authored_date"])


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

    def test_dashboard_query_count_does_not_grow_with_accessible_projects(self) -> None:
        query_counts = []
        for index in range(3):
            project = ProjectFactory.create(created_by=self.user.email)
            UserProjectPermissionFactory.create(
                target=self.user, project=project, level=PermissionLevel.ADMIN
            )
            ProjectCommitFactory.create(project=project, author_email=self.user.email)
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(URL, headers={"authorization": self.auth})
            assert response.status_code == status.HTTP_200_OK
            assert response.data["summary"]["total_projects"] == index + 1
            assert response.data["summary"]["total_commits"] == index + 1
            query_counts.append(len(queries))
        assert query_counts[1:] == [query_counts[0]] * 2

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


class TestDashboardStatsGPSTrackAccess(BaseAPITestCase):
    def test_total_gps_tracks_count(self) -> None:
        _ = GPSTrackFactory.create(creator=self.user)
        inactive = GPSTrackFactory.create(creator=self.user)
        inactive.deactivate(deactivated_by=self.user)
        shared = GPSTrackFactory.create()
        GPSTrackUserPermissionFactory.create(
            user=self.user,
            gps_track=shared,
            level=PermissionLevel.READ_ONLY,
        )
        creator_without_access = GPSTrackFactory.create(creator=self.user)
        creator_without_access.permissions.get(user=self.user).deactivate(
            deactivated_by=self.user
        )

        response = self.client.get(URL, headers={"authorization": self.auth})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["summary"]["total_gps_tracks"] == 2  # noqa: PLR2004
