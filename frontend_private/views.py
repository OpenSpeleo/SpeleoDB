import contextlib
from dataclasses import dataclass

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView
from gitdb.exc import BadName as GitRevBadName
from rest_framework.authtoken.models import Token

from speleodb.git_engine.exceptions import GitCommitNotFoundError
from speleodb.surveys.models import AnyPermissionLevel
from speleodb.surveys.models import Project
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.users.models import SurveyTeam
from speleodb.users.models import User
from speleodb.utils.gitlab_manager import GitlabManager


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


class _BaseTeamView(LoginRequiredMixin, View):
    def get(self, request, team_id: int):
        try:
            team = SurveyTeam.objects.get(id=team_id)
            if request.user and request.user.is_authenticated:
                if not team.is_member(request.user):
                    return redirect(reverse("private:teams"))
                return {"team": team, "is_team_leader": team.is_leader(request.user)}
            return redirect(reverse("home"))
        except ObjectDoesNotExist:
            return redirect(reverse("private:teams"))


class TeamDetailsView(_BaseTeamView):
    template_name = "pages/team/details.html"

    def get(self, request, team_id: int):
        data_or_redirect = super().get(request, team_id=team_id)
        if not isinstance(data_or_redirect, dict):
            return data_or_redirect

        return render(request, TeamDetailsView.template_name, data_or_redirect)


class TeamMembershipsView(_BaseTeamView):
    template_name = "pages/team/memberships.html"

    def get(self, request, team_id: int):
        data_or_redirect = super().get(request, team_id=team_id)
        if not isinstance(data_or_redirect, dict):
            return data_or_redirect

        data_or_redirect["memberships"] = data_or_redirect["team"].get_all_memberships()

        return render(request, TeamMembershipsView.template_name, data_or_redirect)


class TeamDangerZoneView(_BaseTeamView):
    template_name = "pages/team/danger_zone.html"

    def get(self, request, team_id: int):
        data_or_redirect = super().get(request, team_id=team_id)
        if not isinstance(data_or_redirect, dict):
            return data_or_redirect

        if not data_or_redirect["is_team_leader"]:
            return redirect(
                reverse("private:team_details", kwargs={"team_id": team_id})
            )

        return render(request, TeamDangerZoneView.template_name, data_or_redirect)


# ============ Project Pages ============ #
class ProjectListingView(_AuthenticatedTemplateView):
    template_name = "pages/projects.html"


class NewProjectView(_AuthenticatedTemplateView):
    template_name = "pages/project/new.html"


class _BaseProjectView(LoginRequiredMixin, View):
    def get(self, request, project_id: str):
        project = Project.objects.get(id=project_id)
        return {
            "project": project,
            "is_project_admin": project.is_admin(request.user),
            "has_write_access": project.has_write_access(request.user),
        }


class ProjectUploadView(_BaseProjectView):
    template_name = "pages/project/upload.html"

    def get(self, request, project_id: str):
        try:
            data = super().get(request, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        return render(request, ProjectUploadView.template_name, data)


class ProjectDangerZoneView(_BaseProjectView):
    template_name = "pages/project/danger_zone.html"

    def get(self, request, project_id: str):
        try:
            data = super().get(request, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        if not data["is_project_admin"]:
            return redirect(
                reverse("private:project_details", kwargs={"project_id": project_id})
            )

        return render(request, ProjectDangerZoneView.template_name, data)


class ProjectDetailsView(_BaseProjectView):
    template_name = "pages/project/details.html"

    def get(self, request, project_id: str):
        try:
            data = super().get(request, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        return render(request, ProjectDetailsView.template_name, data)


class ProjectUserPermissionsView(_BaseProjectView):
    template_name = "pages/project/user_permissions.html"

    def get(self, request, project_id: str):
        try:
            data = super().get(request, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        # Collecting all the `user` aka. direct permissions of the project
        user_permissions = [
            UserAccessLevel(user=perm.target, level=perm.level_obj)
            for perm in data["project"].get_all_user_permissions()
        ]

        filtered_team_permissions = []

        # Scanning through all the team memberships to collect users who get
        # project access via team permission.
        team_permissions = data["project"].get_all_team_permissions()
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
        return render(request, ProjectUserPermissionsView.template_name, data)


class ProjectTeamPermissionsView(_BaseProjectView):
    template_name = "pages/project/team_permissions.html"

    def get(self, request, project_id: str):
        try:
            data = super().get(request, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        data["permissions"] = data["project"].get_all_team_permissions()
        data["available_teams"] = sorted(
            set(request.user.teams + [perm.target for perm in data["permissions"]]),
            key=lambda team: team.name.upper(),
        )
        return render(request, ProjectTeamPermissionsView.template_name, data)


class ProjectMutexesView(_BaseProjectView):
    template_name = "pages/project/mutex_history.html"

    def get(self, request, project_id: str):
        try:
            data = super().get(request, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        data["mutexes"] = data["project"].rel_mutexes.all().order_by("-creation_date")
        return render(request, ProjectMutexesView.template_name, data)


class ProjectCommitsView(_BaseProjectView):
    template_name = "pages/project/revision_history.html"

    def get(self, request, project_id: str):
        try:
            data = super().get(request, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        project = Project.objects.get(id=project_id)

        data["commits"] = []
        with contextlib.suppress(ValueError):
            project.git_repo.checkout_branch("master")
            data["commits"] = sorted(
                project.git_repo.commits,
                key=lambda commit: commit.date,
                reverse=True,
            )

        data["skip_download_names"] = [
            GitlabManager.FIRST_COMMIT_NAME,
            "Initial Empty",
        ]
        return render(request, ProjectCommitsView.template_name, data)


class ProjectGitExplorerView(_BaseProjectView):
    template_name = "pages/project/git_view.html"

    def get(self, request, project_id: str, hexsha: str | None = None):
        try:
            data = super().get(request, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        project = Project.objects.get(id=project_id)

        # Guard against non-existing commit ID
        try:
            project.git_repo.checkout_branch("master")
            data["n_commits"] = len(list(project.git_repo.commits))
            data["commit"] = project.git_repo.commit(hexsha)
        except (ValueError, GitCommitNotFoundError, GitRevBadName):
            # commit does not exists
            return redirect("private:project_revisions", project_id=project.id)

        return render(request, ProjectGitExplorerView.template_name, data)
