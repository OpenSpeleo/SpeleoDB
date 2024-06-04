from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from speleodb.surveys.models import Project


class _AuthenticatedTemplateView(LoginRequiredMixin, TemplateView):
    login_url = reverse_lazy("account_login")


# ============ Setting Pages ============ #
class DashboardView(_AuthenticatedTemplateView):
    template_name = "pages/settings/dashboard.html"


class FeedbackView(_AuthenticatedTemplateView):
    template_name = "pages/settings/feedback.html"


class NotificationsView(_AuthenticatedTemplateView):
    template_name = "pages/settings/notifications.html"


# ============ Project Pages ============ #
class ProjectView(_AuthenticatedTemplateView):
    template_name = "pages/projects.html"


class ProjectDetailView(LoginRequiredMixin, View):
    template_name = "pages/project/details.html"

    def get(self, request, project_id: str):
        project = Project.objects.get(id=project_id)
        return render(request, ProjectDetailView.template_name, {"project": project})
