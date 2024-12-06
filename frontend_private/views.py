import contextlib

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
from speleodb.surveys.models import Project
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.utils.gitlab_manager import GitlabManager


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
        team = SurveyTeam.objects.get(id=team_id)
        membership = team.get_membership(request.user)
        if request.user and request.user.is_authenticated and membership is not None:
            return {
                "team": team,
                "is_team_leader": membership._role == SurveyTeamMembership.Role.LEADER,  # noqa: SLF001
            }

        raise ObjectDoesNotExist


class TeamDetailsView(_BaseTeamView):
    template_name = "pages/team/details.html"

    def get(self, request, team_id: int):
        try:
            data = super().get(request, team_id=team_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:teams"))
        return render(request, TeamDetailsView.template_name, data)


class TeamMembershipsView(_BaseTeamView):
    template_name = "pages/team/memberships.html"

    def get(self, request, team_id: int):
        try:
            data = super().get(request, team_id=team_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:teams"))

        data["memberships"] = data["team"].get_all_memberships()

        return render(request, TeamMembershipsView.template_name, data)


class TeamDangerZoneView(_BaseTeamView):
    template_name = "pages/team/danger_zone.html"

    def get(self, request, team_id: int):
        try:
            data = super().get(request, team_id=team_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:teams"))

        if not data["is_team_leader"]:
            return redirect(
                reverse("private:team_details", kwargs={"team_id": team_id})
            )

        return render(request, TeamDangerZoneView.template_name, data)


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

        data["permissions"] = data["project"].get_all_user_permissions()
        return render(request, ProjectUserPermissionsView.template_name, data)


class ProjectTeamPermissionsView(_BaseProjectView):
    template_name = "pages/project/team_permissions.html"

    def get(self, request, project_id: str):
        try:
            data = super().get(request, project_id=project_id)
        except ObjectDoesNotExist:
            return redirect(reverse("private:projects"))

        data["permissions"] = data["project"].get_all_team_permissions()
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
