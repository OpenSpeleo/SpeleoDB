# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime
from collections import Counter
from typing import TYPE_CHECKING
from typing import Any

from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework import permissions
from rest_framework.generics import GenericAPIView

from speleodb.gis.models import ExplorationLead
from speleodb.gis.models import SubSurfaceStation
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.users.models import User
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    import uuid

    from rest_framework.request import Request
    from rest_framework.response import Response

    from speleodb.surveys.models import TeamProjectPermission
    from speleodb.surveys.models import UserProjectPermission

    Permission = TeamProjectPermission | UserProjectPermission

RECENT_ACTIVITY_LIMIT = 15
COMMITS_OVER_TIME_MONTHS = 12
CONTRIBUTION_CALENDAR_DAYS = 365


def _first_of_month(dt: datetime.datetime, months_back: int = 0) -> datetime.datetime:
    """Return midnight on the 1st of the month ``months_back`` months before *dt*."""
    m = dt.month - months_back
    y = dt.year
    while m <= 0:
        m += 12
        y -= 1
    return dt.replace(year=y, month=m, day=1, hour=0, minute=0, second=0, microsecond=0)


class UserDashboardStatsView(GenericAPIView[User], SDBAPIViewMixin):
    """Aggregated dashboard statistics for the authenticated user.

    Returns summary counts, permission breakdown, commit time-series,
    contribution calendar, and recent activity in a single request.
    All queries are pure ORM — no git filesystem access.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_user()

        permissions_list: list[Permission] = user.permissions
        project_ids: list[uuid.UUID] = [p.project_id for p in permissions_list]

        summary = self._build_summary(user, project_ids)
        projects_by_level = self._build_projects_by_level(permissions_list)
        projects_by_type = self._build_projects_by_type(project_ids)
        commits_over_time = self._build_commits_over_time(user, project_ids)
        contribution_calendar = self._build_contribution_calendar(user, project_ids)
        recent_activity = self._build_recent_activity(project_ids)

        return SuccessResponse(
            {
                "summary": summary,
                "projects_by_level": projects_by_level,
                "projects_by_type": projects_by_type,
                "commits_over_time": commits_over_time,
                "contribution_calendar": contribution_calendar,
                "recent_activity": recent_activity,
            }
        )

    @staticmethod
    def _build_summary(
        user: User,
        project_ids: list[uuid.UUID],
    ) -> dict[str, int]:
        commit_qs = ProjectCommit.objects.filter(project_id__in=project_ids)

        return {
            "total_projects": len(project_ids),
            "total_teams": user.teams.count(),
            "total_commits": commit_qs.count(),
            "user_commits": commit_qs.filter(author_email=user.email).count(),
            "total_landmarks": user.landmarks.count(),
            "total_gps_tracks": user.gps_tracks.count(),
            "total_stations_created": SubSurfaceStation.objects.filter(
                created_by=user.email
            ).count(),
            "total_exploration_leads": ExplorationLead.objects.filter(
                created_by=user.email,
                project_id__in=project_ids,
            ).count(),
        }

    @staticmethod
    def _build_projects_by_level(
        permissions_list: list[Permission],
    ) -> dict[str, int]:
        """Breakdown by the three collaboration tiers only.

        WEB_VIEWER is intentionally excluded here; it still counts toward
        ``summary.total_projects`` which reports all accessible projects.
        """
        counts: Counter[str] = Counter()
        for perm in permissions_list:
            counts[str(perm.level_label)] += 1
        return {
            "ADMIN": counts.get("ADMIN", 0),
            "READ_AND_WRITE": counts.get("READ_AND_WRITE", 0),
            "READ_ONLY": counts.get("READ_ONLY", 0),
        }

    @staticmethod
    def _build_projects_by_type(
        project_ids: list[uuid.UUID],
    ) -> dict[str, int]:
        rows = (
            Project.objects.filter(id__in=project_ids)
            .values("type")
            .annotate(count=Count("id"))
        )
        return {row["type"]: row["count"] for row in rows}

    @staticmethod
    def _build_commits_over_time(
        user: User,
        project_ids: list[uuid.UUID],
    ) -> list[dict[str, Any]]:
        now = timezone.now()
        start_date = _first_of_month(now, COMMITS_OVER_TIME_MONTHS - 1)

        commit_qs = ProjectCommit.objects.filter(
            project_id__in=project_ids,
            authored_date__gte=start_date,
        )

        total_by_month = dict(
            commit_qs.annotate(month=TruncMonth("authored_date"))
            .values("month")
            .annotate(count=Count("id"))
            .values_list("month", "count")
        )

        user_by_month = dict(
            commit_qs.filter(author_email=user.email)
            .annotate(month=TruncMonth("authored_date"))
            .values("month")
            .annotate(count=Count("id"))
            .values_list("month", "count")
        )

        result: list[dict[str, Any]] = []
        for i in range(COMMITS_OVER_TIME_MONTHS):
            months_back = COMMITS_OVER_TIME_MONTHS - 1 - i
            month_start = _first_of_month(now, months_back)

            month_key = None
            for key in total_by_month:
                if key.year == month_start.year and key.month == month_start.month:
                    month_key = key
                    break

            result.append(
                {
                    "month": month_start.strftime("%Y-%m"),
                    "total": total_by_month.get(month_key, 0) if month_key else 0,
                    "user": user_by_month.get(month_key, 0) if month_key else 0,
                }
            )

        return result

    @staticmethod
    def _build_contribution_calendar(
        user: User,
        project_ids: list[uuid.UUID],
    ) -> list[str]:
        cutoff = timezone.now() - datetime.timedelta(days=CONTRIBUTION_CALENDAR_DAYS)

        timestamps = ProjectCommit.objects.filter(
            project_id__in=project_ids,
            author_email=user.email,
            authored_date__gte=cutoff,
        ).values_list("authored_date", flat=True)

        return [dt.isoformat() for dt in timestamps]

    @staticmethod
    def _build_recent_activity(
        project_ids: list[uuid.UUID],
    ) -> list[dict[str, Any]]:
        commits = (
            ProjectCommit.objects.filter(project_id__in=project_ids)
            .select_related("project")
            .order_by("-authored_date")[:RECENT_ACTIVITY_LIMIT]
        )

        return [
            {
                "commit_id": commit.id,
                "project_name": commit.project.name,
                "project_id": str(commit.project.id),
                "author_name": commit.author_name,
                "author_email": commit.author_email,
                "authored_date": commit.authored_date.isoformat(),
                "message": commit.message,
            }
            for commit in commits
        ]
