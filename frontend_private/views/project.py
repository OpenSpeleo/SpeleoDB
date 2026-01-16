# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.urls import reverse
from rest_framework.authtoken.models import Token

from frontend_private.views.base import AuthenticatedTemplateView
from speleodb.common.enums import PermissionLevel
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectMutex
from speleodb.surveys.models import TeamProjectPermission
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.users.models import User
from speleodb.utils.exceptions import NotAuthorizedError

if TYPE_CHECKING:
    from uuid import UUID

    from django.http import HttpResponse
    from django.http.response import HttpResponseRedirectBase
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


@dataclass
class ProjectInfoData:
    level_label: StrOrPromise
    project: Project
    active_mutex: ProjectMutex | None


class ProjectListingView(AuthenticatedTemplateView):
    template_name = "pages/projects.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        context = self.get_context_data(**kwargs)
        # Filter out projects where user only has WEB_VIEWER access
        perms = [
            perm
            for perm in request.user.permissions
            if perm.level > PermissionLevel.WEB_VIEWER
        ]

        projects = {
            project.pk: project
            for project in (
                Project.objects.with_collaborator_count()  # pyright: ignore[reportAttributeAccessIssue]
                .with_active_mutex()
                .filter(
                    id__in=[perm.project_id for perm in perms]  # pyright: ignore[reportAttributeAccessIssue]
                )
            )
        }

        context["projects_data"] = [
            ProjectInfoData(
                level_label=perm.level_label,
                project=projects[perm.project_id],  # pyright: ignore[reportAttributeAccessIssue]
                active_mutex=(
                    mtx[0]
                    if (mtx := projects[perm.project_id]._prefetched_active_mutex[:1])  # noqa: SLF001 # pyright: ignore[reportAttributeAccessIssue]
                    else None
                )
                or None,
            )
            for perm in perms
        ]

        return self.render_to_response(context)


class NewProjectView(AuthenticatedTemplateView):
    template_name = "pages/project/new.html"


class _BaseProjectView(AuthenticatedTemplateView):
    def get_project_data(self, user: User, project_id: str) -> dict[str, Any]:
        project = Project.objects.with_active_mutex().get(id=project_id)  # pyright: ignore[reportAttributeAccessIssue]

        # Check if user only has WEB_VIEWER access
        try:
            best_permission = project.get_best_permission(user)

            if best_permission.level == PermissionLevel.WEB_VIEWER:
                # User only has WEB_VIEWER access, which is not allowed for these views
                raise PermissionError("Insufficient permissions")

        except (ObjectDoesNotExist, NotAuthorizedError) as e:
            # User has no permissions at all
            raise PermissionError("No permissions for the user found") from e

        return {
            "project": project,
            "is_project_admin": best_permission.level == PermissionLevel.ADMIN,
            "has_write_access": best_permission.level >= PermissionLevel.READ_AND_WRITE,
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
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:projects"))

        project: Project = data["project"]

        data["limit_individual_filesize"] = (
            settings.DJANGO_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT
        )
        data["limit_total_filesize"] = settings.DJANGO_UPLOAD_TOTAL_FILESIZE_MB_LIMIT
        data["limit_number_files"] = settings.DJANGO_UPLOAD_TOTAL_FILES_LIMIT

        # Redirect users who don't own the mutex
        mutex = project.active_mutex
        if mutex is None or mutex.user != request.user:
            return redirect(
                reverse("private:project_mutexes", kwargs={"project_id": project.id})
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

        project: Project = data["project"]

        # Collecting all the `user` aka. direct permissions of the project
        user_permissions = [
            UserAccessLevel(user=perm.target, level=perm.level)
            for perm in project.user_permissions
        ]

        filtered_team_permissions: list[UserAccessLevel] = []

        # Scanning through all the team memberships to collect users who get
        # project access via team permission.
        team_map: dict[UUID, TeamProjectPermission] = {
            team_perm.target_id: team_perm  # pyright: ignore[reportAttributeAccessIssue]
            for team_perm in project.team_permissions
        }

        filtered_team_permissions = [
            UserAccessLevel(
                user=membership.user,
                level=team_map[membership.team_id].level,  # pyright: ignore[reportAttributeAccessIssue]
                team=team_map[membership.team_id].target,  # pyright: ignore[reportAttributeAccessIssue]
            )
            for membership in SurveyTeamMembership.objects.select_related(
                "user"
            ).filter(
                team__in=list(team_map.keys()),
                is_active=True,
            )
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
            project_permissions__project=project,
            project_permissions__is_active=True,
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

        project: Project = data["project"]

        data["mutexes"] = list(
            project.mutexes.select_related("user").order_by("-creation_date")
        )
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
