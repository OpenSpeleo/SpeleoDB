# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any
from typing import override

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import update_last_login
from django.core.exceptions import ObjectDoesNotExist
from django.http.response import HttpResponseRedirectBase
from django.shortcuts import redirect
from django.urls import reverse
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from rest_framework.authtoken.models import Token

from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import Project
from speleodb.surveys.models import TeamPermission
from speleodb.users.models import SurveyTeam
from speleodb.users.models import User

if TYPE_CHECKING:
    from uuid import UUID

    from django.http import HttpResponse
    from django_stubs_ext import StrOrPromise

    from speleodb.utils.requests import AuthenticatedHttpRequest


@dataclass
class UserAccessLevel:
    ALLOWED_ACCESS_LEVELS = PermissionLevel.labels
    user: User
    level: PermissionLevel
    team: SurveyTeam | None = None

    def __init__(
        self, user: User, level: PermissionLevel | int, team: SurveyTeam | None = None
    ) -> None:
        if not isinstance(user, User):
            raise TypeError(f"`user` must be of type User: `{type(self.user)}`")
        self.user = user

        self.level = (
            PermissionLevel.from_value(level) if isinstance(level, int) else level
        )
        if not isinstance(self.level, PermissionLevel):
            raise TypeError(type(self.level))

        self.team = team
        if self.team is not None and not isinstance(self.team, SurveyTeam):
            raise TypeError(
                f"`team` must be of type SurveyTeam | None: `{type(self.team)}`"
            )

    @property
    def level_label(self) -> StrOrPromise:
        """
        Returns the label of the permission level.
        """
        return self.level.label


class _AuthenticatedTemplateView(LoginRequiredMixin, TemplateView):
    login_url = reverse_lazy("account_login")

    def refresh_user_login(self, user: User) -> None:
        with contextlib.suppress(Exception):
            update_last_login(None, user=user)  # type: ignore[arg-type]

    def get(
        self,
        request: AuthenticatedHttpRequest,  # type: ignore[override]
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        render = super().get(request, *args, **kwargs)
        self.refresh_user_login(user=request.user)
        return render


# ============ Setting Pages ============ #
class DashboardView(_AuthenticatedTemplateView):
    template_name = "pages/user/dashboard.html"


class PassWordView(_AuthenticatedTemplateView):
    template_name = "pages/user/password.html"


class AuthTokenView(_AuthenticatedTemplateView):
    template_name = "pages/user/auth-token.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        context = self.get_context_data(**kwargs)
        context["auth_token"], _ = Token.objects.get_or_create(user=request.user)
        return self.render_to_response(context)

    def post(
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        with contextlib.suppress(ObjectDoesNotExist):
            Token.objects.get(user=request.user).delete()

        return self.get(request, *args, **kwargs)


class FeedbackView(_AuthenticatedTemplateView):
    template_name = "pages/user/feedback.html"


class PreferencesView(_AuthenticatedTemplateView):
    template_name = "pages/user/preferences.html"


# ============ Team Pages ============ #
class TeamListingView(_AuthenticatedTemplateView):
    template_name = "pages/teams.html"


class NewTeamView(_AuthenticatedTemplateView):
    template_name = "pages/team/new.html"


class _BaseTeamView(_AuthenticatedTemplateView):
    def get_data_or_redirect(
        self,
        request: AuthenticatedHttpRequest,
        team_id: UUID,
    ) -> HttpResponseRedirectBase | dict[str, SurveyTeam | bool]:
        try:
            team = SurveyTeam.objects.get(id=team_id)
            if request.user and request.user.is_authenticated:
                if not team.is_member(request.user):
                    return redirect(reverse("private:teams"))
            else:
                return redirect(reverse("home"))
        except ObjectDoesNotExist:
            return redirect(reverse("private:teams"))

        return {"team": team, "is_team_leader": team.is_leader(request.user)}


class TeamDetailsView(_BaseTeamView):
    template_name = "pages/team/details.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        team_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse | dict[str, SurveyTeam | bool]:
        data = self.get_data_or_redirect(request, team_id=team_id)
        if isinstance(data, HttpResponseRedirectBase):
            return data

        return super().get(request, *args, **data, **kwargs)


class TeamMembershipsView(_BaseTeamView):
    template_name = "pages/team/memberships.html"

    @override
    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        team_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        data: Any = self.get_data_or_redirect(request, team_id=team_id)
        if isinstance(data, HttpResponseRedirectBase):
            return data

        data["memberships"] = data["team"].get_all_memberships()  # pyright: ignore[reportAttributeAccessIssue]

        return super().get(request, *args, **data, **kwargs)


class TeamDangerZoneView(_BaseTeamView):
    template_name = "pages/team/danger_zone.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        team_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        data = self.get_data_or_redirect(request, team_id=team_id)
        if not isinstance(data, dict):
            return data  # redirection

        if not data["is_team_leader"]:
            return redirect(
                reverse("private:team_details", kwargs={"team_id": team_id})
            )

        return super().get(request, *args, **data, **kwargs)


# ============ Project Pages ============ #
class ProjectListingView(_AuthenticatedTemplateView):
    template_name = "pages/projects.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        context = self.get_context_data(**kwargs)
        # Filter out projects where user only has WEB_VIEWER access
        context["filtered_permissions"] = [
            perm
            for perm in request.user.permissions
            if perm.level > PermissionLevel.WEB_VIEWER
        ]
        return self.render_to_response(context)


class NewProjectView(_AuthenticatedTemplateView):
    template_name = "pages/project/new.html"


class _BaseProjectView(_AuthenticatedTemplateView):
    def get_project_data(self, user: User, project_id: str) -> dict[str, Any]:
        project = Project.objects.get(id=project_id)

        # Check if user only has WEB_VIEWER access
        try:
            best_permission = project.get_best_permission(user)
            if best_permission.level == PermissionLevel.WEB_VIEWER:
                # User only has WEB_VIEWER access, which is not allowed for these views
                raise PermissionError("Insufficient permissions")
        except ObjectDoesNotExist as e:
            # User has no permissions at all
            raise PermissionError("No permissions") from e

        return {
            "project": project,
            "is_project_admin": project.is_admin(user),
            "has_write_access": project.has_write_access(user),
        }


class ProjectUploadView(_BaseProjectView):
    template_name = "pages/project/upload.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        project_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
            data["limit_individual_filesize"] = (
                settings.DJANGO_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT
            )
            data["limit_total_filesize"] = (
                settings.DJANGO_UPLOAD_TOTAL_FILESIZE_MB_LIMIT
            )
            data["limit_number_files"] = settings.DJANGO_UPLOAD_TOTAL_FILES_LIMIT
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:projects"))

        # Redirect users who don't own the mutex
        mutex = data["project"].active_mutex
        if mutex is None or mutex.user != request.user:
            return redirect(
                reverse(
                    "private:project_mutexes", kwargs={"project_id": data["project"].id}
                )
            )

        return super().get(request, *args, **data, **kwargs)


class ProjectDangerZoneView(_BaseProjectView):
    template_name = "pages/project/danger_zone.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        project_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:projects"))

        if not data["is_project_admin"]:
            return redirect(
                reverse("private:project_details", kwargs={"project_id": project_id})
            )

        return super().get(request, *args, **data, **kwargs)


class ProjectDetailsView(_BaseProjectView):
    template_name = "pages/project/details.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        project_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:projects"))

        return super().get(request, *args, **data, **kwargs)


class ProjectUserPermissionsView(_BaseProjectView):
    template_name = "pages/project/user_permissions.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        project_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:projects"))

        # Collecting all the `user` aka. direct permissions of the project
        user_permissions = [
            UserAccessLevel(user=perm.target, level=perm.level)
            for perm in data["project"].user_permissions
        ]

        filtered_team_permissions: list[UserAccessLevel] = []

        # Scanning through all the team memberships to collect users who get
        # project access via team permission.
        team_permissions: list[TeamPermission] = data["project"].team_permissions

        filtered_team_permissions = [
            UserAccessLevel(
                user=membership.user,
                level=team_permission.level,
                team=team_permission.target,
            )
            for team_permission in team_permissions
            for membership in team_permission.target.get_all_memberships()
        ]

        # Keeping the best permission for each user
        permission_map: dict[User, UserAccessLevel] = {}
        for permission in filtered_team_permissions:
            if (
                permission.user not in permission_map
                or permission_map[permission.user].level.value < permission.level.value
            ):
                permission_map[permission.user] = permission

        # Merging everything together with user permissions first to appear on top
        data["permissions"] = user_permissions + sorted(
            permission_map.values(),
            key=lambda perm: (-perm.level.value, perm.user.email),
        )

        return super().get(request, *args, **data, **kwargs)


class ProjectTeamPermissionsView(_BaseProjectView):
    template_name = "pages/project/team_permissions.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        project_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:projects"))

        project: Project = data["project"]
        data["permissions"] = project.team_permissions

        project_teams = SurveyTeam.objects.filter(
            rel_permissions__project=project,
            rel_permissions__is_active=True,
        )

        data["available_teams"] = sorted(
            [team for team in request.user.teams if team not in project_teams],
            key=lambda team: team.name.upper(),
        )

        return super().get(request, *args, **data, **kwargs)


class ProjectMutexesView(_BaseProjectView):
    template_name = "pages/project/mutex_history.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        project_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:projects"))

        data["mutexes"] = data["project"].rel_mutexes.all().order_by("-creation_date")

        return super().get(request, *args, **data, **kwargs)


class ProjectRevisionHistoryView(_BaseProjectView):
    template_name = "pages/project/revision_history.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        project_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:projects"))

        return super().get(request, *args, **data, **kwargs)


class ProjectGitExplorerView(_BaseProjectView):
    template_name = "pages/project/git_view.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        project_id: str,
        hexsha: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:projects"))

        data["hexsha"] = hexsha

        return super().get(request, *args, **data, **kwargs)


class ProjectGitInstructionsView(_BaseProjectView):
    template_name = "pages/project/git_instructions.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        project_id: str,
        hexsha: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:projects"))

        data["auth_token"], _ = Token.objects.get_or_create(user=request.user)
        data["default_branch"] = settings.DJANGO_GIT_BRANCH_NAME

        return super().get(request, *args, **data, **kwargs)


class MapViewerView(_AuthenticatedTemplateView):
    template_name = "pages/map_viewer.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        if not (request.user.has_beta_access()):
            return redirect(reverse("private:projects"))

        survey_projects = [
            project for project in request.user.projects if not project.exclude_geojson
        ]

        # Convert projects to a JSON-serializable format
        projects_data = [
            {
                "id": str(project.id),
                "name": project.name,
                "modified_date": project.modified_date.isoformat(),
                "permissions": project.get_best_permission(request.user).level_label,
            }
            for project in survey_projects
        ]

        # Check if user has write access to any project
        # For map viewer, we'll grant write access if user has write access
        # to any project
        has_write_access = any(
            project.has_write_access(request.user) for project in survey_projects
        )

        data = {
            "projects": json.dumps(projects_data),
            "has_write_access": has_write_access,
        }
        return super().get(request, *args, **data, **kwargs)
