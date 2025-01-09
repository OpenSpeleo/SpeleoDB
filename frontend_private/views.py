import contextlib
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import update_last_login
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.urls import reverse
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from rest_framework.authtoken.models import Token

from speleodb.surveys.models import AnyPermissionLevel
from speleodb.surveys.models import Project
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.users.models import SurveyTeam
from speleodb.users.models import User


@dataclass
class UserAccessLevel:
    ALLOWED_ACCESS_LEVELS = set(
        UserPermission.Level.labels + TeamPermission.Level.labels
    )
    user: User
    # level: str
    level: AnyPermissionLevel
    team: SurveyTeam | None = None

    def __post_init__(self):
        if not isinstance(self.user, User):
            raise TypeError(f"`user` must be of type User: `{type(self.user)}`")

        if self.team is not None and not isinstance(self.team, SurveyTeam):
            raise TypeError(
                f"`team` must be of type SurveyTeam | None: `{type(self.team)}`"
            )

        if not isinstance(self.level, (UserPermission.Level, TeamPermission.Level)):
            raise TypeError(type(self.level))


class _AuthenticatedTemplateView(LoginRequiredMixin, TemplateView):
    login_url = reverse_lazy("account_login")

    def refresh_user_login(self, user: User) -> None:
        with contextlib.suppress(Exception):
            update_last_login(None, user=user)

    def get(self, request, *args, **kwargs):
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

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context["auth_token"], _ = Token.objects.get_or_create(user=request.user)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
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
    def get_data_or_redirect(self, request, team_id: int):
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

    def get(self, request, team_id: int, *args, **kwargs):
        data = self.get_data_or_redirect(request, team_id=team_id)
        if not isinstance(data, dict):
            return data  # redirection

        return super().get(request, *args, **data, **kwargs)


class TeamMembershipsView(_BaseTeamView):
    template_name = "pages/team/memberships.html"

    def get(self, request, team_id: int, *args, **kwargs):
        data = self.get_data_or_redirect(request, team_id=team_id)
        if not isinstance(data, dict):
            return data  # redirection

        data["memberships"] = data["team"].get_all_memberships()

        return super().get(request, *args, **data, **kwargs)


class TeamDangerZoneView(_BaseTeamView):
    template_name = "pages/team/danger_zone.html"

    def get(self, request, team_id: int, *args, **kwargs):
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


class NewProjectView(_AuthenticatedTemplateView):
    template_name = "pages/project/new.html"


class _BaseProjectView(_AuthenticatedTemplateView):
    def get_project_data(self, user: User, project_id: str) -> dict:
        project = Project.objects.get(id=project_id)
        return {
            "project": project,
            "is_project_admin": project.is_admin(user),
            "has_write_access": project.has_write_access(user),
        }


class ProjectUploadView(_BaseProjectView):
    template_name = "pages/project/upload.html"

    def get(self, request, project_id: str, *args, **kwargs):
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
            data["limit_individual_filesize"] = (
                settings.DJANGO_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT
            )
            data["limit_total_filesize"] = (
                settings.DJANGO_UPLOAD_TOTAL_FILESIZE_MB_LIMIT
            )
            data["limit_number_files"] = settings.DJANGO_UPLOAD_TOTAL_FILES_LIMIT
        except ObjectDoesNotExist:
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

    def get(self, request, project_id: str, *args, **kwargs):
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        if not data["is_project_admin"]:
            return redirect(
                reverse("private:project_details", kwargs={"project_id": project_id})
            )

        return super().get(request, *args, **data, **kwargs)


class ProjectDetailsView(_BaseProjectView):
    template_name = "pages/project/details.html"

    def get(self, request, project_id: str, *args, **kwargs):
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        return super().get(request, *args, **data, **kwargs)


class ProjectUserPermissionsView(_BaseProjectView):
    template_name = "pages/project/user_permissions.html"

    def get(self, request, project_id: str, *args, **kwargs):
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        # Collecting all the `user` aka. direct permissions of the project
        user_permissions = [
            UserAccessLevel(user=perm.target, level=perm.level_obj)
            for perm in data["project"].user_permissions
        ]

        filtered_team_permissions = []

        # Scanning through all the team memberships to collect users who get
        # project access via team permission.
        team_permissions = data["project"].team_permissions
        for team_permission in team_permissions:
            for membership in team_permission.target.get_all_memberships():
                filtered_team_permissions.append(  # noqa: PERF401
                    UserAccessLevel(
                        user=membership.user,
                        level=team_permission.level_obj,
                        team=team_permission.target,
                    )
                )

        # Keeping the best permission for each user
        permission_map = {}
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

    def get(self, request, project_id: str, *args, **kwargs):
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        project: Project = data["project"]
        data["permissions"] = project.team_permissions

        project_teams = SurveyTeam.objects.filter(rel_permissions__project=project)

        data["available_teams"] = sorted(
            [team for team in request.user.teams if team not in project_teams],
            key=lambda team: team.name.upper(),
        )

        return super().get(request, *args, **data, **kwargs)


class ProjectMutexesView(_BaseProjectView):
    template_name = "pages/project/mutex_history.html"

    def get(self, request, project_id: str, *args, **kwargs):
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        data["mutexes"] = data["project"].rel_mutexes.all().order_by("-creation_date")

        return super().get(request, *args, **data, **kwargs)


class ProjectRevisionHistoryView(_BaseProjectView):
    template_name = "pages/project/revision_history.html"

    def get(self, request, project_id: str, *args, **kwargs):
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        return super().get(request, *args, **data, **kwargs)


class ProjectGitExplorerView(_BaseProjectView):
    template_name = "pages/project/git_view.html"

    def get(self, request, project_id: str, hexsha: str | None = None, *args, **kwargs):
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        data["hexsha"] = hexsha

        return super().get(request, *args, **data, **kwargs)


class ProjectGitInstructionsView(_BaseProjectView):
    template_name = "pages/project/git_instructions.html"

    def get(self, request, project_id: str, hexsha: str | None = None, *args, **kwargs):
        try:
            data = self.get_project_data(user=request.user, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        data["auth_token"], _ = Token.objects.get_or_create(user=request.user)
        data["default_branch"] = settings.DJANGO_GIT_BRANCH_NAME

        return super().get(request, *args, **data, **kwargs)
